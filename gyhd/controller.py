# -*- coding: utf-8 -*-
"""Qt 后端门面：UI 只需要和 AppController 打交道。

界面开发者请把 ``AppController`` 当成唯一后端入口：
    * 启动：``controller.start()``（main.py 已调用）
    * 退出：``controller.shutdown()``（aboutToQuit 已连接）
    * 其余能力见 docs/UI_CONTRACT.md
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from . import autostart
from .config import Config, ConfigStore
from .constants import STAGES
from .guard_worker import GuardWorker
from .wallpaper import WallpaperError
from .wallpaper_service import perform_wallpaper_change
from .wps_guard import RecorderKill, WpsGuard

logger = logging.getLogger(__name__)


class AppController(QObject):
    wallpaper_changed = pyqtSignal(str)
    wallpaper_failed = pyqtSignal(str)
    config_changed = pyqtSignal(object)
    slideshow_changed = pyqtSignal(bool)
    wps_running_changed = pyqtSignal(bool)
    recorder_blocked = pyqtSignal(str, int)
    recorder_detected = pyqtSignal(str, int)
    monitoring_changed = pyqtSignal(bool)
    autostart_changed = pyqtSignal(bool)
    error = pyqtSignal(str)

    def __init__(
        self,
        config_store: ConfigStore | None = None,
        parent: QObject | None = None,
        *,
        dry_run_override: bool = False,
    ) -> None:
        super().__init__(parent)
        self._store = config_store or ConfigStore()
        try:
            self._config = self._store.load()
        except Exception:  # noqa: BLE001 - 配置坏了也必须能启动
            logger.exception("加载配置失败，使用默认配置")
            self._config = Config().normalized()
        self._worker: GuardWorker | None = None
        self._started = False
        self._last_guard_error = ""
        self._last_kill_error = ""
        # 命令行 --dry-run 只影响本次运行，绝不写回 config.toml。
        self._dry_run_override = bool(dry_run_override)

    @property
    def config(self) -> Config:
        return self._config

    @property
    def autostart_enabled(self) -> bool:
        return autostart.is_enabled()

    @property
    def dry_run_active(self) -> bool:
        """本次运行是否处于演练模式（命令行覆盖优先于配置）。"""
        return self._dry_run_override or self._config.guard_dry_run

    @property
    def monitoring(self) -> bool:
        return self._worker is not None

    def start(self) -> None:
        if self._started:
            return
        self._started = True

        # 启动时自动检查“启动”文件夹里的快捷方式；用户取消勾选后
        # config.autostart=false，这里就不会再自动创建。
        if self._config.autostart:
            try:
                autostart.ensure_shortcut()
            except Exception as exc:  # noqa: BLE001
                logger.exception("自动创建开机自启快捷方式失败")
                self.error.emit(f"自动创建开机自启快捷方式失败：{exc}")
        else:
            autostart.remove_legacy_run_entry()
        self.autostart_changed.emit(autostart.is_enabled())

        if self._config.change_wallpaper_on_start:
            QTimer.singleShot(0, self.change_wallpaper)
        if self._config.guard_enabled:
            self._start_guard()
        else:
            self.monitoring_changed.emit(False)

    def shutdown(self) -> None:
        self._stop_guard()
        self._save()
        self._started = False

    def change_wallpaper(self) -> str | None:
        try:
            path = perform_wallpaper_change(self._config)
        except WallpaperError as exc:
            logger.warning("更换壁纸失败：%s", exc)
            self.wallpaper_failed.emit(str(exc))
            return None
        except Exception as exc:  # noqa: BLE001
            logger.exception("更换壁纸时发生未预期错误")
            self.wallpaper_failed.emit(f"更换壁纸时发生未预期错误：{exc}")
            return None
        logger.info("更换壁纸成功：%s", path)
        self.wallpaper_changed.emit(str(path))
        return str(path)

    def set_stage(self, stage: str) -> None:
        if stage not in STAGES:
            self.error.emit(f"未知的学段：{stage}")
            return
        self._config.stage = stage
        self._save()
        self.config_changed.emit(self._config)

    def set_weather_enabled(self, enabled: bool) -> None:
        self._config.weather_enabled = bool(enabled)
        self._save()
        self.config_changed.emit(self._config)

    def set_wallpaper_folder(self, folder: str) -> bool:
        candidate = Path(str(folder)).expanduser()
        try:
            candidate = candidate.resolve()
        except OSError:
            self.error.emit(f"文件夹不可访问：{folder}")
            return False
        if not candidate.is_dir():
            self.error.emit(f"文件夹不存在：{candidate}")
            return False
        self._config.wallpaper_folder = str(candidate)
        self._save()
        self.config_changed.emit(self._config)
        return True

    def set_change_wallpaper_on_start(self, enabled: bool) -> None:
        self._config.change_wallpaper_on_start = bool(enabled)
        self._save()
        self.config_changed.emit(self._config)

    def set_minimize_to_tray(self, enabled: bool) -> None:
        self._config.minimize_to_tray = bool(enabled)
        self._save()
        self.config_changed.emit(self._config)

    def set_guard_enabled(self, enabled: bool) -> None:
        self._config.guard_enabled = bool(enabled)
        self._save()
        self.config_changed.emit(self._config)
        if not self._started:
            return
        if enabled:
            self._start_guard()
        else:
            self._stop_guard()

    def set_kill_only_during_slideshow(self, enabled: bool) -> None:
        self._config.kill_only_during_slideshow = bool(enabled)
        self._save()
        self.config_changed.emit(self._config)
        self._restart_guard_if_running()

    def set_guard_dry_run(self, enabled: bool) -> None:
        self._config.guard_dry_run = bool(enabled)
        self._save()
        self.config_changed.emit(self._config)
        self._restart_guard_if_running()

    def set_autostart(self, enabled: bool) -> bool:
        target = bool(enabled)
        try:
            autostart.set_enabled(target)
        except OSError as exc:
            logger.exception("设置开机自启失败")
            self.error.emit(f"设置开机自启失败：{exc}")
            self.autostart_changed.emit(autostart.is_enabled())
            return False
        actual = autostart.is_enabled()
        if actual == target:
            self._config.autostart = target
            self._save()
            self.config_changed.emit(self._config)
        else:
            self.error.emit(
                "设置开机自启失败：快捷方式和注册表都没有写入成功，"
                "请检查“启动”文件夹权限。"
            )
        self.autostart_changed.emit(actual)
        return actual == target

    def _restart_guard_if_running(self) -> None:
        if self._worker is None:
            return
        self._stop_guard()
        if self._config.guard_enabled:
            self._start_guard()

    def _start_guard(self) -> None:
        if self._worker is not None:
            return
        if self.dry_run_active:
            logger.warning("演练模式已开启：只记录检测结果，不会结束录屏进程")
        guard = WpsGuard(
            kill_only_during_slideshow=self._config.kill_only_during_slideshow,
            dry_run=self.dry_run_active,
        )
        worker = GuardWorker(guard, self._config.guard_interval_ms, parent=self)
        worker.slideshow_changed.connect(self._on_slideshow)
        worker.wps_running_changed.connect(self.wps_running_changed)
        worker.recorder_killed.connect(self._on_killed)
        worker.recorder_detected.connect(self._on_detected)
        worker.kill_failed.connect(self._on_kill_failed)
        worker.poll_failed.connect(self._on_poll_failed)
        worker.start()
        self._worker = worker
        self.monitoring_changed.emit(True)

    def _stop_guard(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.stop()
            worker.deleteLater()
            self.monitoring_changed.emit(False)

    def _on_slideshow(self, active: bool) -> None:
        logger.info("WPS 放映状态：%s", "进行中" if active else "已结束")
        self.slideshow_changed.emit(active)

    def _on_killed(self, kill: RecorderKill) -> None:
        logger.warning(
            "已结束 WPS 录屏进程：%s (PID %s, %s)", kill.name, kill.pid, kill.exe
        )
        self.recorder_blocked.emit(kill.name or "录屏程序", kill.pid)

    def _on_detected(self, kill: RecorderKill) -> None:
        logger.info(
            "演练模式：检测到 WPS 录屏进程 %s (PID %s)，未结束",
            kill.name,
            kill.pid,
        )
        self.recorder_detected.emit(kill.name or "录屏程序", kill.pid)

    def _on_kill_failed(self, process) -> None:
        message = (
            f"无法结束录屏进程 {process.name} (PID {process.pid})，可能需要管理员权限"
        )
        logger.warning(message)
        if message != self._last_kill_error:
            self._last_kill_error = message
            self.error.emit(message)

    def _on_poll_failed(self, message: str) -> None:
        logger.warning("守护轮询失败：%s", message)
        if message != self._last_guard_error:
            self._last_guard_error = message
            self.error.emit(f"后台守护异常：{message}")

    def _save(self) -> None:
        try:
            self._store.save(self._config)
        except OSError as exc:
            logger.exception("保存配置失败")
            self.error.emit(f"保存配置失败：{exc}")
