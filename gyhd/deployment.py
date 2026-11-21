# -*- coding: utf-8 -*-
"""把程序自身部署到 D 盘，并在部署后从新位置重新启动。

规则：
    * 运行后检查 ``D:\\GYHD-Enhancement-Changyan`` 是否已经有完整程序；
    * 没有就复制过去，然后从 D 盘重新启动，当前进程退出；
    * D 盘不存在、没有写权限或复制失败时只记日志，继续从当前位置运行，不阻塞用户；
    * 用 ``--skip-deploy`` 或环境变量 ``GYHD_SKIP_DEPLOY=1`` 可跳过（调试用）。
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .constants import DEFAULT_INSTALL_DIR

logger = logging.getLogger(__name__)

INSTALL_DIR_ENV = "GYHD_INSTALL_DIR"
SKIP_DEPLOY_ENV = "GYHD_SKIP_DEPLOY"

_IGNORE = shutil.ignore_patterns(
    ".git",
    ".gitignore",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    "tests",
    "_tmp",
    "runtime",
    "runtime2",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.spec",
    "*.log",
    "config.toml",
    "config.json",
    "config.json.migrated-*",
    "config.*.broken-*",
    ".idea",
    ".vscode",
    "Thumbs.db",
    "desktop.ini",
)


@dataclass(frozen=True)
class ShortcutSpec:
    target: Path
    arguments: str
    working_dir: Path
    icon: Path | None


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def is_onefile() -> bool:
    if not is_frozen():
        return False
    mei = getattr(sys, "_MEIPASS", None)
    return not mei or Path(mei).name.startswith("_MEI")


def current_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def install_dir() -> Path:
    override = os.environ.get(INSTALL_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path(DEFAULT_INSTALL_DIR)


def pythonw_executable() -> Path:
    executable = Path(sys.executable)
    if executable.name.casefold() == "pythonw.exe":
        return executable
    candidate = executable.with_name("pythonw.exe")
    return candidate if candidate.exists() else executable


def is_installed(target: Path | None = None, *, frozen: bool | None = None) -> bool:
    target = Path(target) if target is not None else install_dir()
    frozen = is_frozen() if frozen is None else frozen
    if frozen:
        return (target / Path(sys.executable).name).is_file()
    return (target / "main.py").is_file() and (target / "gyhd" / "__init__.py").is_file()


def should_deploy() -> bool:
    if os.environ.get(SKIP_DEPLOY_ENV) == "1":
        return False
    if not Path("D:\\").exists():
        return False
    source = current_root()
    target = install_dir()
    try:
        source = source.resolve()
        target = target.resolve()
    except OSError:
        return False
    if source == target:
        return False
    try:
        target.relative_to(source)
    except ValueError:
        pass
    else:
        # 目标在源码目录里面，复制会递归，直接跳过。
        return False
    return not is_installed(target)


def launch_command(root: Path, extra_args: Sequence[str]) -> list[str]:
    if is_frozen():
        return [str(Path(root) / Path(sys.executable).name), *extra_args]
    return [
        str(pythonw_executable()),
        str(Path(root) / "main.py"),
        *extra_args,
    ]


def shortcut_spec(root: Path | None = None) -> ShortcutSpec:
    root = Path(root) if root is not None else current_root()
    if is_frozen():
        target = root / Path(sys.executable).name
        return ShortcutSpec(
            target=target,
            arguments="--startup",
            working_dir=root,
            icon=target,
        )
    main_py = root / "main.py"
    icon = root / "assets" / "GY_1080x1080.ico"
    return ShortcutSpec(
        target=pythonw_executable(),
        arguments=subprocess.list2cmdline([str(main_py), "--startup"]),
        working_dir=root,
        icon=icon if icon.is_file() else None,
    )


def autostart_root() -> Path:
    """自启快捷方式优先指向 D 盘已安装副本，否则指向当前位置。"""
    target = install_dir()
    return target if is_installed(target) else current_root()


def copy_app_tree(source: Path, target: Path) -> None:
    source = Path(source)
    target = Path(target)
    if source.resolve() == target.resolve():
        return
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True, ignore=_IGNORE)


def _copy_onefile(target: Path) -> None:
    executable = Path(sys.executable)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(executable, target / executable.name)
    mei = Path(getattr(sys, "_MEIPASS", executable.parent))
    assets = mei / "assets"
    if not assets.is_dir():
        assets = executable.parent / "assets"
    if assets.is_dir():
        shutil.copytree(assets, target / "assets", dirs_exist_ok=True)


def _relaunch(target: Path, argv: Sequence[str]) -> None:
    args = [arg for arg in argv if arg != "--skip-deploy"]
    args.append("--skip-deploy")
    command = launch_command(target, args)
    logger.info("从新位置重新启动：%s", subprocess.list2cmdline(command))
    subprocess.Popen(
        command,
        cwd=str(target),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


def deploy_and_relaunch(argv: Sequence[str]) -> bool:
    """需要部署时复制并重启；返回 True 表示当前进程应该退出。"""
    if not should_deploy():
        return False

    target = install_dir()
    try:
        if is_frozen():
            if is_onefile():
                _copy_onefile(target)
            else:
                copy_app_tree(current_root(), target)
        else:
            copy_app_tree(current_root(), target)
        logger.info("已把程序复制到：%s", target)
        _relaunch(target, argv)
        return True
    except Exception:  # noqa: BLE001 - 部署失败不能阻止程序启动
        logger.exception("部署到 %s 失败，继续从当前位置运行", target)
        return False
