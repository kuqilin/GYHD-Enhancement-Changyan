# -*- coding: utf-8 -*-
"""顶层窗口枚举：用于识别 WPS 演示的全屏放映窗口。"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import os
from dataclasses import dataclass

from .winproc import process_path

logger = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)

MONITOR_DEFAULTTONEAREST = 2

EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

user32.EnumWindows.argtypes = [EnumWindowsProc, wt.LPARAM]
user32.EnumWindows.restype = wt.BOOL
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsWindowVisible.restype = wt.BOOL
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetWindowRect.restype = wt.BOOL
user32.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
user32.MonitorFromWindow.restype = wt.HANDLE
user32.GetMonitorInfoW.argtypes = [wt.HANDLE, ctypes.c_void_p]
user32.GetMonitorInfoW.restype = wt.BOOL


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("rcMonitor", wt.RECT),
        ("rcWork", wt.RECT),
        ("dwFlags", wt.DWORD),
    ]


Rect = tuple[int, int, int, int]


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    pid: int
    process_name: str
    class_name: str
    title: str
    visible: bool
    rect: Rect
    monitor_rect: Rect | None

    def is_fullscreen(self, tolerance: int = 4) -> bool:
        if self.monitor_rect is None:
            return False
        return all(
            abs(left - right) <= tolerance
            for left, right in zip(self.rect, self.monitor_rect)
        )


def _class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def _window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _window_rect(hwnd: int) -> Rect:
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return (rect.left, rect.top, rect.right, rect.bottom)


def _monitor_rect(hwnd: int) -> Rect | None:
    monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    if not monitor:
        return None
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        rect = info.rcMonitor
        return (rect.left, rect.top, rect.right, rect.bottom)
    return None


def list_top_level_windows(*, only_visible: bool = True) -> list[WindowInfo]:
    windows: list[WindowInfo] = []
    path_cache: dict[int, str] = {}

    @EnumWindowsProc
    def callback(hwnd, _lparam):
        try:
            visible = bool(user32.IsWindowVisible(hwnd))
            if only_visible and not visible:
                return True
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            pid_value = int(pid.value)
            if pid_value not in path_cache:
                path_cache[pid_value] = process_path(pid_value)
            exe = path_cache[pid_value]
            windows.append(
                WindowInfo(
                    hwnd=int(hwnd),
                    pid=pid_value,
                    process_name=os.path.basename(exe),
                    class_name=_class_name(hwnd),
                    title=_window_title(hwnd),
                    visible=visible,
                    rect=_window_rect(hwnd),
                    monitor_rect=_monitor_rect(hwnd),
                )
            )
        except Exception:
            logger.debug("枚举窗口时跳过 hwnd=%s", hwnd, exc_info=True)
        return True

    if not user32.EnumWindows(callback, 0):
        logger.debug("EnumWindows 返回 0，Win32 错误=%s", ctypes.get_last_error())
    return windows
