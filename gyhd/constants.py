# -*- coding: utf-8 -*-
"""项目级常量与路径解析。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_ID = "GYHD-Enhancement-Changyan"
APP_NAME = "花都校区畅言增强工具"
APP_NAME_FULL = "花都校区畅言增强工具"
APP_VERSION = "0.3.3"
ORG_NAME = "kuqilin"
GITHUB_URL = "https://github.com/kuqilin/GYHD-Enhancement-Changyan"

DEFAULT_WALLPAPER_FOLDER = r"D:\花都校区定制壁纸"
DEFAULT_INSTALL_DIR = r"D:\GYHD-Enhancement-Changyan"
SUPPORTED_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".gif")

STAGES = ("高一", "高二", "高三", "初一", "初二", "初三")
HIGH_SCHOOL_STAGES = frozenset({"高一", "高二", "高三"})
MIDDLE_SCHOOL_STAGES = frozenset({"初一", "初二", "初三"})
DEFAULT_STAGE = "高三"

# 广东广雅中学（花都校区）附近；换城市改这里即可。
WEATHER_LATITUDE = 23.39
WEATHER_LONGITUDE = 113.22
WEATHER_TIMEZONE = "Asia/Shanghai"
WEATHER_CITY = "广州"

# WPS 演示 / WPS Office 主程序。WPS 12 起，放映窗口实际由 wpp.exe 创建，
# 但也见过 wps.exe 承载放映窗口的版本，所以两个都接受。
WPS_PROCESS_NAMES = frozenset({"wpp.exe", "wps.exe"})

# WPS 的“录屏”功能由 ApowerREC 提供，插件目录形如：
# %APPDATA%\Kingsoft\wps\addons\pool\win-i386\kapower_2.2.0.7\kapowerapp\ApowerREC.exe
RECORDER_NAME_MARKERS = ("apowerrec", "kapower", "wpsrecorder", "wpsrecord")
RECORDER_PATH_MARKERS = ("apowerrec", "\\kapower_", "\\kapower\\")

SLIDESHOW_TITLE_MARKERS = ("slide show", "slideshow", "幻灯片放映")
# “放映”单独出现时也可能只是文件名，必须配合放映窗口类名才认。
SLIDESHOW_WEAK_TITLE_MARKERS = ("放映",)

RUN_REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def app_data_dir() -> Path:
    """可写的用户数据目录：%LOCALAPPDATA%\\GYHD-Enhancement-Changyan。"""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Local")
    return Path(base) / APP_ID


def config_path() -> Path:
    return app_data_dir() / "config.toml"


def log_dir() -> Path:
    return app_data_dir() / "logs"


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resource_path(relative: str) -> Path:
    """兼容源码运行与 PyInstaller（onefile/onedir）的资源定位。"""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = project_root()
    return base / relative


def icon_path() -> Path:
    return resource_path("assets/GY_1080x1080.ico")
