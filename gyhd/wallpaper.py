# -*- coding: utf-8 -*-
"""Windows 壁纸切换（纯 ctypes，不依赖 pywin32）。"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import os
import random
import winreg
from pathlib import Path
from typing import Callable, Sequence

from .constants import SUPPORTED_IMAGE_EXTS

logger = logging.getLogger(__name__)

SPI_SETDESKWALLPAPER = 0x0014
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02
DESKTOP_KEY = r"Control Panel\Desktop"

SpiFunction = Callable[[str, int], bool]


class WallpaperError(RuntimeError):
    """壁纸切换失败。"""


def list_images(folder: str | os.PathLike[str]) -> list[Path]:
    root = Path(folder)
    if not root.is_dir():
        return []
    images: list[Path] = []
    try:
        entries = list(root.iterdir())
    except OSError:
        logger.exception("无法列出壁纸文件夹：%s", root)
        return []
    for entry in entries:
        try:
            if entry.is_file() and entry.suffix.lower() in SUPPORTED_IMAGE_EXTS:
                images.append(entry)
        except OSError:
            continue
    images.sort(key=lambda path: path.name.casefold())
    return images


def pick_random_image(
    images: Sequence[Path],
    current: str | None = None,
    rng: random.Random | None = None,
) -> Path:
    if not images:
        raise WallpaperError("没有可用的图片")
    chooser = rng or random
    candidates = list(images)
    if len(candidates) > 1 and current:
        current_key = os.path.normcase(os.path.abspath(current))
        filtered = [
            path
            for path in candidates
            if os.path.normcase(os.path.abspath(str(path))) != current_key
        ]
        if filtered:
            candidates = filtered
    return chooser.choice(candidates)


def current_wallpaper() -> str:
    """读取注册表里当前壁纸路径，失败时返回空串。"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, DESKTOP_KEY) as key:
            value, _ = winreg.QueryValueEx(key, "Wallpaper")
        return str(value)
    except OSError:
        return ""


def _set_fill_style() -> None:
    """Win10/11 上把壁纸设为“填充”，避免被系统的幻灯片模式改回去。"""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, DESKTOP_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "10")
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0")
    except OSError:
        logger.debug("写入壁纸填充样式失败（不影响设置壁纸）", exc_info=True)


def _spi_set_wallpaper(image_path: str, flags: int) -> bool:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SystemParametersInfoW.argtypes = [wt.UINT, wt.UINT, wt.LPCWSTR, wt.UINT]
    user32.SystemParametersInfoW.restype = wt.BOOL
    return bool(
        user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, image_path, flags)
    )


def set_wallpaper(
    image_path: str | os.PathLike[str],
    *,
    spi: SpiFunction | None = None,
    apply_style: bool = True,
) -> Path:
    path = Path(image_path).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise WallpaperError(f"壁纸文件不存在：{path}") from exc
    if not resolved.is_file():
        raise WallpaperError(f"壁纸路径不是文件：{resolved}")

    if apply_style:
        _set_fill_style()

    setter = spi or _spi_set_wallpaper
    flags = SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
    if not setter(str(resolved), flags):
        error_code = ctypes.get_last_error()
        raise WallpaperError(
            "设置壁纸失败：SystemParametersInfoW 返回 0"
            f"（Win32 错误 {error_code}）"
        )
    logger.info("壁纸已设置：%s", resolved)
    return resolved


def change_to_random(
    folder: str | os.PathLike[str],
    *,
    spi: SpiFunction | None = None,
    rng: random.Random | None = None,
    avoid_current: bool = True,
) -> Path:
    images = list_images(folder)
    if not images:
        raise WallpaperError(f"文件夹不存在或里面没有支持的图片：{folder}")
    current = current_wallpaper() if avoid_current else None
    chosen = pick_random_image(images, current=current, rng=rng)
    return set_wallpaper(chosen, spi=spi)
