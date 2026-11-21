# -*- coding: utf-8 -*-
"""把 WpsGuard 放进 QThread，避免轮询阻塞 Qt 事件循环。"""

from __future__ import annotations

import logging
import threading
import time

from PyQt5.QtCore import QThread, pyqtSignal

from .wps_guard import GuardSnapshot, RecorderKill, WpsGuard

logger = logging.getLogger(__name__)


class GuardWorker(QThread):
    slideshow_changed = pyqtSignal(bool)
    wps_running_changed = pyqtSignal(bool)
    recorder_killed = pyqtSignal(object)  # RecorderKill
    recorder_detected = pyqtSignal(object)  # RecorderKill（演练模式）
    kill_failed = pyqtSignal(object)  # ProcessInfo
    poll_failed = pyqtSignal(str)

    def __init__(self, guard: WpsGuard, interval_ms: int = 500, parent=None) -> None:
        super().__init__(parent)
        self._guard = guard
        self._interval = max(0.05, interval_ms / 1000.0)
        self._stop_event = threading.Event()
        self._last_slideshow: bool | None = None
        self._last_wps: bool | None = None
        # 演练模式下同一 PID 只报一次，避免每 500ms 刷一行日志。
        self._reported_dry_run_pids: set[int] = set()

    def run(self) -> None:
        while not self._stop_event.is_set():
            started = time.monotonic()
            try:
                snapshot = self._guard.poll()
            except Exception as exc:  # noqa: BLE001 - 后台线程必须活着
                logger.exception("WPS 守护轮询失败")
                self.poll_failed.emit(f"{type(exc).__name__}: {exc}")
            else:
                self._emit(snapshot)
            elapsed = time.monotonic() - started
            self._stop_event.wait(max(0.05, self._interval - elapsed))

    def _emit(self, snapshot: GuardSnapshot) -> None:
        if snapshot.slideshow_active != self._last_slideshow:
            self._last_slideshow = snapshot.slideshow_active
            self.slideshow_changed.emit(snapshot.slideshow_active)
        if snapshot.wps_running != self._last_wps:
            self._last_wps = snapshot.wps_running
            self.wps_running_changed.emit(snapshot.wps_running)
        for kill in snapshot.killed:
            self.recorder_killed.emit(kill)
        for kill in snapshot.would_kill:
            if kill.pid not in self._reported_dry_run_pids:
                self._reported_dry_run_pids.add(kill.pid)
                self.recorder_detected.emit(kill)
        # 进程退出后允许同一 PID（理论上少见）或下一次启动重新上报。
        self._reported_dry_run_pids &= {
            process.pid for process in snapshot.recorders
        }
        for process in snapshot.failures:
            self.kill_failed.emit(process)

    def stop(self) -> None:
        self._stop_event.set()
        if self.isRunning():
            self.wait(5000)
