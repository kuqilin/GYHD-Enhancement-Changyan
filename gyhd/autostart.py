# -*- coding: utf-8 -*-
"""开机自启：在“启动”文件夹里创建指向本程序的快捷方式。

和旧版的区别：
    * 不再写 HKCU 的 Run 项，改成真正的 .lnk 快捷方式；
    * 快捷方式参数固定为 ``--startup``：不显示主界面，只换壁纸并进入后台守护；
    * 若 pywin32 不可用，会降级回注册表 Run 项，至少保证开机自启不失效。
"""

from __future__ import annotations

import logging
import os
import subprocess
import winreg
from pathlib import Path

from . import deployment
from .constants import APP_ID, APP_NAME_FULL, RUN_REGISTRY_KEY

logger = logging.getLogger(__name__)

_start_menu_appdata = os.environ.get("APPDATA") or str(
    Path.home() / "AppData" / "Roaming"
)
STARTUP_DIR = (
    Path(_start_menu_appdata)
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / "Startup"
)
SHORTCUT_PATH = STARTUP_DIR / f"{APP_ID}.lnk"


def shortcut_path() -> Path:
    return SHORTCUT_PATH


def _same_path(left: str | os.PathLike[str], right: str | os.PathLike[str]) -> bool:
    try:
        left_path = os.path.normcase(os.path.abspath(str(left)))
        right_path = os.path.normcase(os.path.abspath(str(right)))
    except OSError:
        return False
    return left_path == right_path


def _run_entry_exists() -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_REGISTRY_KEY,
            0,
            winreg.KEY_QUERY_VALUE,
        ) as key:
            value, _ = winreg.QueryValueEx(key, APP_ID)
        return bool(value)
    except OSError:
        return False


def _delete_run_entry() -> None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_REGISTRY_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, APP_ID)
        logger.info("已清理旧的 HKCU Run 自启项")
    except FileNotFoundError:
        pass
    except OSError:
        logger.exception("清理旧的自启注册表项失败")


def _write_run_entry(command: str) -> None:
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        RUN_REGISTRY_KEY,
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(key, APP_ID, 0, winreg.REG_SZ, command)
    logger.warning("创建快捷方式失败，已降级为 HKCU Run 自启：%s", command)


def _command_line(spec: deployment.ShortcutSpec) -> str:
    base = subprocess.list2cmdline([str(spec.target)])
    return f"{base} {spec.arguments}".strip()


def _shortcut_matches(shell, spec: deployment.ShortcutSpec) -> bool:
    try:
        existing = shell.CreateShortCut(str(SHORTCUT_PATH))
        return (
            _same_path(existing.TargetPath, spec.target)
            and existing.Arguments.strip() == spec.arguments.strip()
            and _same_path(existing.WorkingDirectory, spec.working_dir)
        )
    except Exception:  # noqa: BLE001 - 读不到就当不匹配，重写
        return False


def ensure_shortcut() -> bool:
    """确保启动快捷方式存在且指向当前安装位置。返回是否成功创建 .lnk。"""
    root = deployment.autostart_root()
    spec = deployment.shortcut_spec(root)

    try:
        import win32com.client  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("pywin32 未安装，无法创建 .lnk 快捷方式")
        _write_run_entry(_command_line(spec))
        return False

    try:
        STARTUP_DIR.mkdir(parents=True, exist_ok=True)
        shell = win32com.client.Dispatch("WScript.Shell")
        if SHORTCUT_PATH.is_file() and _shortcut_matches(shell, spec):
            _delete_run_entry()
            logger.debug("开机自启快捷方式已存在：%s", SHORTCUT_PATH)
            return True

        link = shell.CreateShortCut(str(SHORTCUT_PATH))
        link.TargetPath = str(spec.target)
        link.Arguments = spec.arguments
        link.WorkingDirectory = str(spec.working_dir)
        if spec.icon is not None and spec.icon.is_file():
            link.IconLocation = f"{spec.icon},0"
        link.Description = APP_NAME_FULL
        link.save()
        _delete_run_entry()
        logger.info(
            "已创建开机自启快捷方式：%s -> %s %s",
            SHORTCUT_PATH,
            spec.target,
            spec.arguments,
        )
        return True
    except Exception:  # noqa: BLE001 - 快捷方式失败不能阻止程序启动
        logger.exception("创建开机自启快捷方式失败")
        try:
            _write_run_entry(_command_line(spec))
        except OSError:
            logger.exception("降级写入 HKCU Run 也失败")
        return False


def is_enabled() -> bool:
    return SHORTCUT_PATH.is_file() or _run_entry_exists()


def set_enabled(enabled: bool) -> None:
    if enabled:
        ensure_shortcut()
        return

    try:
        SHORTCUT_PATH.unlink(missing_ok=True)
    except OSError:
        logger.exception("删除开机自启快捷方式失败：%s", SHORTCUT_PATH)
    _delete_run_entry()
    logger.info("已关闭开机自启")


def remove_legacy_run_entry() -> None:
    _delete_run_entry()


def command() -> str:
    spec = deployment.shortcut_spec(deployment.autostart_root())
    return _command_line(spec)


def enable() -> None:
    set_enabled(True)


def disable() -> None:
    set_enabled(False)
