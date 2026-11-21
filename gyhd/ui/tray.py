# -*- coding: utf-8 -*-
"""系统托盘入口。"""

from __future__ import annotations

from PyQt5.QtCore import QObject
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QMenu,
    QStyle,
    QSystemTrayIcon,
    QWidget,
)

from ..constants import APP_NAME_FULL, icon_path
from ..controller import AppController


class TrayIcon(QObject):
    def __init__(
        self,
        controller: AppController,
        window: QWidget,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._window = window
        self._available = QSystemTrayIcon.isSystemTrayAvailable()

        icon = QIcon(str(icon_path()))
        if icon.isNull():
            icon = window.style().standardIcon(QStyle.SP_ComputerIcon)
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip(APP_NAME_FULL)

        self._menu = QMenu()
        self._show_action = QAction("显示主界面", self._menu)
        self._wallpaper_action = QAction("立即更换壁纸", self._menu)
        self._pause_action = QAction("暂停守护", self._menu)
        self._pause_action.setCheckable(True)
        self._quit_action = QAction("退出", self._menu)
        self._menu.addAction(self._show_action)
        self._menu.addAction(self._wallpaper_action)
        self._menu.addSeparator()
        self._menu.addAction(self._pause_action)
        self._menu.addSeparator()
        self._menu.addAction(self._quit_action)
        self._tray.setContextMenu(self._menu)

        self._show_action.triggered.connect(self._show_window)
        self._wallpaper_action.triggered.connect(controller.change_wallpaper)
        self._pause_action.toggled.connect(
            lambda paused: controller.set_guard_enabled(not paused)
        )
        self._quit_action.triggered.connect(QApplication.quit)
        self._tray.activated.connect(self._on_activated)

        controller.monitoring_changed.connect(self._sync_pause_action)
        self._sync_pause_action(controller.monitoring)

    @property
    def available(self) -> bool:
        return self._available

    def show(self) -> None:
        if self._available:
            self._tray.show()

    def _show_window(self) -> None:
        self._window.show_and_raise()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._show_window()

    def _sync_pause_action(self, monitoring: bool) -> None:
        self._pause_action.blockSignals(True)
        self._pause_action.setChecked(not monitoring)
        self._pause_action.blockSignals(False)
        self._tray.setToolTip(
            f"{APP_NAME_FULL}\n后台守护：{'运行中' if monitoring else '已暂停'}"
        )
