# -*- coding: utf-8 -*-
"""占位主界面：能完整跑通后端，界面样式由你继续改。

重做界面时只需要保留：
    MainWindow(controller) 构造函数
    show_and_raise() / set_tray_available(bool)
    closeEvent 里的“最小化到托盘”逻辑（可选）
"""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QTime
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..constants import APP_NAME_FULL, STAGES
from ..controller import AppController
from ..countdown import exam_info
from ..wallpaper import list_images


def _set_checked(widget: QCheckBox, checked: bool) -> None:
    widget.blockSignals(True)
    widget.setChecked(checked)
    widget.blockSignals(False)


class MainWindow(QMainWindow):
    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._can_minimize_to_tray = False
        self._tray_hint_shown = False
        self._kill_count = 0

        self.setWindowTitle(APP_NAME_FULL)
        self.resize(760, 740)
        self.setMinimumSize(720, 720)
        self._build_ui()
        self._connect_signals()
        self._sync_from_config()
        self._append_log("程序已启动，等待后台守护就绪…")

    # ---------- UI ----------

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel(APP_NAME_FULL)
        title_font = title.font()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        subtitle = QLabel("随机壁纸 · WPS 放映时自动结束误触的录屏程序")
        subtitle.setObjectName("subtitleLabel")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        layout.addWidget(self._build_wallpaper_group())
        layout.addWidget(self._build_guard_group())
        layout.addWidget(self._build_behavior_group())

        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(800)
        self.log_view.setMinimumHeight(90)
        self.log_view.setPlaceholderText("运行日志会显示在这里")
        layout.addWidget(self.log_view, 1)

        bottom = QHBoxLayout()
        self.tray_btn = QPushButton("隐藏到托盘")
        self.quit_btn = QPushButton("退出")
        bottom.addStretch(1)
        bottom.addWidget(self.tray_btn)
        bottom.addWidget(self.quit_btn)
        layout.addLayout(bottom)

        self.setCentralWidget(central)
        self.statusBar().showMessage("就绪")
        self.setStyleSheet(
            """
            QLineEdit, QPlainTextEdit {
                border: 1px solid #cfcfcf;
                border-radius: 6px;
                background: #ffffff;
            }
            QPushButton {
                border: 1px solid #c8c8c8;
                border-radius: 6px;
                background: #f7f7f7;
            }
            QPushButton:hover { background: #eeeeee; }
            QLabel#subtitleLabel, QLabel#hintLabel { color: #666666; }
            """
        )

    def _build_wallpaper_group(self) -> QGroupBox:
        box = QGroupBox("桌面壁纸")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(6)
        row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("尚未设置壁纸文件夹")
        self.browse_btn = QPushButton("浏览…")
        self.change_btn = QPushButton("立即更换")
        row.addWidget(self.path_edit, 1)
        row.addWidget(self.browse_btn)
        row.addWidget(self.change_btn)
        layout.addLayout(row)

        stage_row = QHBoxLayout()
        stage_row.addWidget(QLabel("学段"))
        self.stage_combo = QComboBox()
        self.stage_combo.setObjectName("combo_stage")
        self.stage_combo.addItems(STAGES)
        self.stage_combo.setMinimumWidth(96)
        stage_row.addWidget(self.stage_combo)
        self.countdown_label = QLabel("")
        self.countdown_label.setObjectName("label_countdown")
        stage_row.addWidget(self.countdown_label, 1)
        layout.addLayout(stage_row)

        self.wallpaper_status = QLabel("等待第一次更换…")
        self.wallpaper_status.setWordWrap(True)
        layout.addWidget(self.wallpaper_status)
        return box

    def _build_guard_group(self) -> QGroupBox:
        box = QGroupBox("WPS 放映守护")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(6)
        self.guard_check = QCheckBox("启用后台守护")
        self.only_slideshow_check = QCheckBox("只在 PPT 全屏放映时拦截")
        checks = QHBoxLayout()
        checks.addWidget(self.guard_check)
        checks.addWidget(self.only_slideshow_check)
        checks.addStretch(1)
        layout.addLayout(checks)

        self.slideshow_label = QLabel("○ 未检测到放映")
        self.slideshow_label.setStyleSheet("color: #777777;")
        self.kill_count_label = QLabel("已拦截录屏：0 次")
        status = QHBoxLayout()
        status.addWidget(self.slideshow_label)
        status.addWidget(self.kill_count_label)
        status.addStretch(1)
        layout.addLayout(status)

        self.dry_run_label = QLabel("⚠ 演练模式：只记录，不结束录屏进程")
        self.dry_run_label.setStyleSheet("color: #b26a00; font-weight: 600;")
        self.dry_run_label.setVisible(self._controller.dry_run_active)
        layout.addWidget(self.dry_run_label)

        hint = QLabel("命中 ApowerREC / kapower 录屏进程时自动结束。")
        hint.setObjectName("hintLabel")
        layout.addWidget(hint)
        return box

    def _build_behavior_group(self) -> QGroupBox:
        box = QGroupBox("行为")
        grid = QGridLayout(box)
        grid.setContentsMargins(10, 6, 10, 8)
        grid.setSpacing(8)
        self.start_change_check = QCheckBox("启动时自动换一张壁纸")
        self.autostart_check = QCheckBox("开机自动启动（当前用户）")
        self.minimize_check = QCheckBox("关闭窗口时最小化到托盘")
        self.weather_check = QCheckBox("在壁纸上显示当天气温")
        grid.addWidget(self.start_change_check, 0, 0)
        grid.addWidget(self.autostart_check, 0, 1)
        grid.addWidget(self.minimize_check, 1, 0)
        grid.addWidget(self.weather_check, 1, 1)
        return box

    # ---------- signals ----------

    def _connect_signals(self) -> None:
        self.browse_btn.clicked.connect(self._browse)
        self.change_btn.clicked.connect(self._change_wallpaper)
        self.stage_combo.currentTextChanged.connect(self._on_stage_changed)
        self.guard_check.toggled.connect(self._controller.set_guard_enabled)
        self.only_slideshow_check.toggled.connect(
            self._controller.set_kill_only_during_slideshow
        )
        self.start_change_check.toggled.connect(
            self._controller.set_change_wallpaper_on_start
        )
        self.minimize_check.toggled.connect(self._controller.set_minimize_to_tray)
        self.weather_check.toggled.connect(self._controller.set_weather_enabled)
        self.autostart_check.toggled.connect(self._toggle_autostart)
        self.tray_btn.clicked.connect(self.hide)
        self.quit_btn.clicked.connect(QApplication.quit)

        self._controller.wallpaper_changed.connect(self._on_wallpaper_changed)
        self._controller.wallpaper_failed.connect(self._on_wallpaper_failed)
        self._controller.slideshow_changed.connect(self._on_slideshow_changed)
        self._controller.recorder_blocked.connect(self._on_recorder_blocked)
        self._controller.recorder_detected.connect(self._on_recorder_detected)
        self._controller.monitoring_changed.connect(self._on_monitoring_changed)
        self._controller.autostart_changed.connect(self._on_autostart_changed)
        self._controller.config_changed.connect(self._on_config_changed)
        self._controller.error.connect(self._on_error)

    # ---------- actions ----------

    def _browse(self) -> None:
        start = self.path_edit.text() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "选择壁纸文件夹", start)
        if not folder:
            return
        if not self._controller.set_wallpaper_folder(folder):
            QMessageBox.warning(
                self, "保存失败", "文件夹不存在或不可访问，详情请看运行日志。"
            )
            return
        self.path_edit.setText(folder)
        count = len(list_images(folder))
        self._append_log(f"壁纸文件夹已更新：{folder}（{count} 张图片）")
        if count == 0:
            QMessageBox.warning(
                self,
                "文件夹里没有图片",
                "已保存路径，但里面没有 .jpg / .png / .bmp / .gif 文件。",
            )

    def _change_wallpaper(self) -> None:
        self.wallpaper_status.setText("正在换壁纸并写倒计时…")
        if self._controller.change_wallpaper() is None:
            self.wallpaper_status.setText("更换失败，详情见运行日志")

    def _on_stage_changed(self, stage: str) -> None:
        if stage != self._controller.config.stage:
            self._controller.set_stage(stage)
        self._update_countdown_label()

    def _update_countdown_label(self) -> None:
        info = exam_info(self._controller.config.stage)
        self.countdown_label.setText(
            f"距离{info.exam} {info.days} 天 · {info.target.isoformat()}"
        )

    def _toggle_autostart(self, enabled: bool) -> None:
        if not self._controller.set_autostart(enabled):
            _set_checked(self.autostart_check, self._controller.autostart_enabled)

    # ---------- controller slots ----------

    def _on_wallpaper_changed(self, path: str) -> None:
        stamp = QTime.currentTime().toString("HH:mm:ss")
        self.wallpaper_status.setText(f"上次更换：{stamp}\n{path}")
        self._append_log(f"壁纸已更换：{path}")

    def _on_wallpaper_failed(self, message: str) -> None:
        self.wallpaper_status.setText(f"更换失败：{message}")
        self._append_log(f"更换失败：{message}")

    def _on_slideshow_changed(self, active: bool) -> None:
        if active:
            self.slideshow_label.setText("● 正在放映 PPT，守护已生效")
            self.slideshow_label.setStyleSheet("color: #1a7f37; font-weight: 600;")
        else:
            self.slideshow_label.setText("○ 未检测到放映")
            self.slideshow_label.setStyleSheet("color: #777777;")

    def _on_recorder_blocked(self, name: str, pid: int) -> None:
        self._kill_count += 1
        self.kill_count_label.setText(f"已拦截录屏：{self._kill_count} 次")
        self._append_log(f"已结束录屏进程：{name} (PID {pid})")
        self.statusBar().showMessage(f"已拦截 WPS 录屏：{name}", 5000)

    def _on_recorder_detected(self, name: str, pid: int) -> None:
        self._append_log(f"演练模式：检测到录屏进程 {name} (PID {pid})，未结束")

    def _on_monitoring_changed(self, enabled: bool) -> None:
        _set_checked(self.guard_check, enabled)
        self.only_slideshow_check.setEnabled(enabled)
        if enabled and self._controller.dry_run_active:
            self._append_log("后台守护已开启（演练模式，不会结束录屏进程）")
        else:
            self._append_log("后台守护已开启" if enabled else "后台守护已暂停")

    def _on_autostart_changed(self, enabled: bool) -> None:
        _set_checked(self.autostart_check, enabled)
        self._append_log("已开启开机自启" if enabled else "已关闭开机自启")

    def _on_config_changed(self, _config) -> None:
        self._sync_from_config()

    def _on_error(self, message: str) -> None:
        self._append_log(message)
        self.statusBar().showMessage(message, 5000)

    # ---------- helpers ----------

    def _sync_from_config(self) -> None:
        config = self._controller.config
        self.path_edit.setText(config.wallpaper_folder)
        self.stage_combo.blockSignals(True)
        self.stage_combo.setCurrentText(config.stage)
        self.stage_combo.blockSignals(False)
        self._update_countdown_label()
        _set_checked(self.guard_check, config.guard_enabled)
        _set_checked(self.only_slideshow_check, config.kill_only_during_slideshow)
        _set_checked(self.start_change_check, config.change_wallpaper_on_start)
        _set_checked(self.minimize_check, config.minimize_to_tray)
        _set_checked(self.weather_check, config.weather_enabled)
        _set_checked(self.autostart_check, self._controller.autostart_enabled)
        self.only_slideshow_check.setEnabled(config.guard_enabled)
        self.dry_run_label.setVisible(self._controller.dry_run_active)

    def _append_log(self, message: str) -> None:
        stamp = QTime.currentTime().toString("HH:mm:ss")
        self.log_view.appendPlainText(f"[{stamp}] {message}")

    def set_tray_available(self, available: bool) -> None:
        self._can_minimize_to_tray = bool(available)
        self.tray_btn.setEnabled(bool(available))

    def show_and_raise(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        if self._can_minimize_to_tray and self._controller.config.minimize_to_tray:
            event.ignore()
            self.hide()
            if not self._tray_hint_shown:
                self._tray_hint_shown = True
                self.statusBar().showMessage("已隐藏到托盘，双击托盘图标可重新打开", 5000)
            return
        event.accept()
        QApplication.quit()
