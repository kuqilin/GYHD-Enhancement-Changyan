# -*- coding: utf-8 -*-
"""WPS 放映守护：识别 PPT 全屏放映，并结束误触启动的 WPS 录屏进程。

WPS 的“录屏”入口并不是 WPS 自身实现的，而是调用随插件分发的 ApowerREC：

    %APPDATA%\\Kingsoft\\wps\\addons\\pool\\win-i386\\
        kapower_<版本>\\kapowerapp\\ApowerREC.exe

实测 WPS 12.1 的放映窗口特征（见 README）：
    * 进程：wpp.exe
    * 窗口类：Qt5QWindowIcon
    * 标题：WPS Presentation Slide Show - [文件名]
    * 覆盖整个显示器（无边框全屏）
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Callable, Sequence

from . import winproc, winwindow
from .constants import (
    RECORDER_NAME_MARKERS,
    RECORDER_PATH_MARKERS,
    SLIDESHOW_TITLE_MARKERS,
    SLIDESHOW_WEAK_TITLE_MARKERS,
    WPS_PROCESS_NAMES,
)
from .winproc import ProcessInfo
from .winwindow import WindowInfo

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecorderKill:
    pid: int
    name: str
    exe: str
    timestamp: float


@dataclass(frozen=True)
class GuardSnapshot:
    slideshow_active: bool
    wps_running: bool
    recorders: tuple[ProcessInfo, ...] = ()
    killed: tuple[RecorderKill, ...] = ()
    would_kill: tuple[RecorderKill, ...] = ()
    failures: tuple[ProcessInfo, ...] = ()
    checked_at: float = 0.0


def is_wps_process(name: str) -> bool:
    return name.casefold() in WPS_PROCESS_NAMES


def is_slideshow_window(
    window: WindowInfo,
    *,
    title_markers: Sequence[str] = SLIDESHOW_TITLE_MARKERS,
    weak_title_markers: Sequence[str] = SLIDESHOW_WEAK_TITLE_MARKERS,
) -> bool:
    if not window.visible or not is_wps_process(window.process_name):
        return False

    title = window.title.casefold()
    class_name = window.class_name.casefold()
    # 放映窗口的类名实测是 Qt5QWindowIcon；别的版本可能叫 PP12ShowFrame 之类。
    looks_like_show_class = class_name.startswith("qt5qwindow") or "show" in class_name

    if any(marker.casefold() in title for marker in title_markers):
        return window.is_fullscreen() or looks_like_show_class
    if any(marker.casefold() in title for marker in weak_title_markers):
        return looks_like_show_class
    # 标题被本地化或被改掉时的兜底：Qt 全屏无边框窗口。
    return looks_like_show_class and window.is_fullscreen()


def is_recorder_process(process: ProcessInfo) -> bool:
    name = (process.name or os.path.basename(process.exe)).casefold()
    if not name:
        return False
    if any(marker in name for marker in RECORDER_NAME_MARKERS):
        return True
    exe = (process.exe or "").casefold().replace("/", "\\")
    if not exe.endswith(".exe"):
        return False
    return any(marker in exe for marker in RECORDER_PATH_MARKERS)


class WpsGuard:
    """一次 poll() 完成“探测放映 + 扫描/结束录屏”的完整轮询。"""

    def __init__(
        self,
        *,
        kill_only_during_slideshow: bool = True,
        dry_run: bool = False,
        window_lister: Callable[[], list[WindowInfo]] | None = None,
        process_lister: Callable[[], list[ProcessInfo]] | None = None,
        killer: Callable[[int], bool] | None = None,
        clock: Callable[[], float] = time.monotonic,
        self_pid: int | None = None,
    ) -> None:
        self.kill_only_during_slideshow = bool(kill_only_during_slideshow)
        self.dry_run = bool(dry_run)
        self._window_lister = window_lister or winwindow.list_top_level_windows
        self._process_lister = process_lister or winproc.list_processes
        self._killer = killer or winproc.terminate_process
        self._clock = clock
        self._self_pid = os.getpid() if self_pid is None else self_pid

    def poll(self) -> GuardSnapshot:
        checked_at = self._clock()
        windows = self._window_lister()
        processes = self._process_lister()

        slideshow_active = any(is_slideshow_window(window) for window in windows)
        wps_running = any(
            is_wps_process(window.process_name) for window in windows
        ) or any(is_wps_process(process.name) for process in processes)

        recorders = tuple(
            process
            for process in processes
            if process.pid != self._self_pid and is_recorder_process(process)
        )

        should_kill = bool(recorders) and (
            not self.kill_only_during_slideshow or slideshow_active
        )
        killed: list[RecorderKill] = []
        would_kill: list[RecorderKill] = []
        failures: list[ProcessInfo] = []

        if should_kill:
            for process in recorders:
                record = RecorderKill(
                    pid=process.pid,
                    name=process.name,
                    exe=process.exe,
                    timestamp=checked_at,
                )
                if self.dry_run:
                    would_kill.append(record)
                elif self._killer(process.pid):
                    killed.append(record)
                else:
                    failures.append(process)

        return GuardSnapshot(
            slideshow_active=slideshow_active,
            wps_running=wps_running,
            recorders=recorders,
            killed=tuple(killed),
            would_kill=tuple(would_kill),
            failures=tuple(failures),
            checked_at=checked_at,
        )
