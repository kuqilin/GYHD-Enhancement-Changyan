# -*- coding: utf-8 -*-
"""开机自启：写入 HKCU 的 Run 项，无需管理员权限。

旧项目用启动文件夹快捷方式；这里用注册表 Run 项，命令里的路径全部是绝对路径，
因此不会重蹈“开机时 CWD 是 System32，读不到 config.json”的覆辙。
"""

from __future__ import annotations

import logging
import subprocess
import sys
import winreg
from pathlib import Path

from .constants import APP_ID, RUN_REGISTRY_KEY

logger = logging.getLogger(__name__)


def _launcher() -> str:
    executable = Path(sys.executable)
    if getattr(sys, "frozen", False):
        return str(executable)
    pythonw = executable.with_name("pythonw.exe")
    return str(pythonw if pythonw.exists() else executable)


def main_script() -> Path:
    return Path(__file__).resolve().parents[1] / "main.py"


def command() -> str:
    if getattr(sys, "frozen", False):
        parts = [sys.executable, "--minimized"]
    else:
        parts = [_launcher(), str(main_script()), "--minimized"]
    return subprocess.list2cmdline(parts)


def is_enabled() -> bool:
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


def set_enabled(enabled: bool) -> None:
    if enabled:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            RUN_REGISTRY_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, APP_ID, 0, winreg.REG_SZ, command())
        logger.info("已开启开机自启：%s", command())
        return

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_REGISTRY_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, APP_ID)
        logger.info("已关闭开机自启")
    except FileNotFoundError:
        pass


def enable() -> None:
    set_enabled(True)


def disable() -> None:
    set_enabled(False)
