# Qt Designer 界面清单

这份是给 Designer 用的“最少需要什么”。按表拖控件、改 `objectName`，然后在
`gyhd/ui/main_window.py` 里接线即可。后端只认 `AppController`，不认具体控件名；
你换名字也行，只要适配层跟着改。

## 1. 根窗口

- 推荐 `QMainWindow`，对象名 `MainWindow`
- `pyuic5` 生成的类名是 `Ui_MainWindow`
- 如果根控件用 `QWidget`，生成的类名是 `Ui_Form`，适配层基类也要改成 `QWidget`

`main.py` 固定从 `gyhd.ui.main_window` 导入 `MainWindow`，并这样调用：

```python
window = MainWindow(controller)
window.set_tray_available(tray.available)
tray.show()
controller.start()
if not startup_mode:
    window.show()
```

所以适配层必须保留：

| 接口 | 用途 |
| --- | --- |
| `MainWindow(controller, parent=None)` | 构造签名 |
| `show_and_raise()` | 托盘“显示主界面”调用 |
| `set_tray_available(bool)` | 告诉窗口能不能最小化到托盘 |
| `closeEvent(event)` | 关闭时隐藏到托盘或退出（建议保留） |

## 2. 控件清单

“必需”是后端/主流程要用的；“可选”是体验项，不加也能跑。

| 控件 | 类型 | 建议 objectName | 必需 | 用途 |
| --- | --- | --- | --- | --- |
| 壁纸路径 | `QLineEdit` | `lineEdit_path` | 是 | 显示当前文件夹，只读 |
| 浏览 | `QPushButton` | `btn_browse` | 是 | 选文件夹并保存 |
| 立即更换 | `QPushButton` | `btn_change` | 是 | 换壁纸 + 写倒计时/气温 |
| 学段 | `QComboBox` | `combo_stage` | 是 | 高一/高二/高三/初一/初二/初三 |
| 倒计时 | `QLabel` | `label_countdown` | 是 | 显示“距离高考 197 天 · 2027-06-07” |
| 壁纸状态 | `QLabel` | `label_wallpaper_status` | 建议 | 上次更换时间/失败原因 |
| 守护开关 | `QCheckBox` | `check_guard` | 是 | 启用后台 WPS 守护 |
| 只在放映时 | `QCheckBox` | `check_only_show` | 是 | 只在 PPT 全屏放映时拦截 |
| 放映状态 | `QLabel` | `label_slideshow` | 建议 | “正在放映/未检测到” |
| 拦截次数 | `QLabel` | `label_kill_count` | 建议 | 累计结束录屏次数 |
| 演练模式提示 | `QLabel` | `label_dry_run` | 可选 | 演练模式时显示警告 |
| 启动换壁纸 | `QCheckBox` | `check_change_on_start` | 可选 | 对应 `change_wallpaper_on_start` |
| 开机自启 | `QCheckBox` | `check_autostart` | 建议 | 创建/删除启动文件夹快捷方式 |
| 关闭到托盘 | `QCheckBox` | `check_minimize_to_tray` | 可选 | 对应 `minimize_to_tray` |
| 显示气温 | `QCheckBox` | `check_weather` | 可选 | 对应 `weather_enabled` |
| 日志 | `QPlainTextEdit` | `plainText_log` | 建议 | 只读，追加运行日志 |
| 隐藏到托盘 | `QPushButton` | `btn_tray` | 可选 | `self.hide()` |
| 退出 | `QPushButton` | `btn_quit` | 是 | `QApplication.quit()` |

学段下拉框按顺序加入：

```python
from gyhd.constants import STAGES  # ("高一","高二","高三","初一","初二","初三")
```

## 3. 控件信号 → controller

| 控件信号 | 连接到 |
| --- | --- |
| `btn_browse.clicked` | 自己的 `_browse()`：`QFileDialog.getExistingDirectory`，再 `controller.set_wallpaper_folder(path)` |
| `btn_change.clicked` | `controller.change_wallpaper` |
| `combo_stage.currentTextChanged` | `controller.set_stage` |
| `check_guard.toggled` | `controller.set_guard_enabled` |
| `check_only_show.toggled` | `controller.set_kill_only_during_slideshow` |
| `check_change_on_start.toggled` | `controller.set_change_wallpaper_on_start` |
| `check_autostart.toggled` | `controller.set_autostart`（返回 bool，失败要恢复勾选） |
| `check_minimize_to_tray.toggled` | `controller.set_minimize_to_tray` |
| `check_weather.toggled` | `controller.set_weather_enabled` |
| `btn_quit.clicked` | `QApplication.quit` |
| `btn_tray.clicked` | `self.hide` |

不要自己写 `config.toml`，也不要直接改 `controller.config` 的字段；全部走 setter，
才会保存并通知界面。

## 4. controller 信号 → 控件

| 信号 | 参数 | 建议更新 |
| --- | --- | --- |
| `wallpaper_changed` | `str` 图片路径 | 状态标签、日志 |
| `wallpaper_failed` | `str` 错误 | 状态标签、日志；启动时不要弹模态 |
| `config_changed` | `Config` 对象 | 回填路径/学段/复选框（先 `blockSignals`） |
| `slideshow_changed` | `bool` | 放映状态标签 |
| `wps_running_changed` | `bool` | 可选：WPS 是否运行 |
| `recorder_blocked` | `str` 名称, `int` PID | 拦截次数 +1、日志 |
| `recorder_detected` | `str` 名称, `int` PID | 演练模式日志 |
| `monitoring_changed` | `bool` | 守护开关/提示 |
| `autostart_changed` | `bool` | 自启复选框 |
| `error` | `str` | 日志/状态栏，不要每次都弹窗 |

`config_changed` 里回填复选框时一定要：

```python
widget.blockSignals(True)
widget.setChecked(value)
widget.blockSignals(False)
```

否则 `setChecked()` 会触发 `toggled`，又写一遍配置。

## 5. 初始状态

在 `MainWindow.__init__` 里，`setupUi` 之后、`controller.start()` 之前做一次：

```python
cfg = controller.config
self.lineEdit_path.setText(cfg.wallpaper_folder)
self.combo_stage.setCurrentText(cfg.stage)
self.check_guard.setChecked(cfg.guard_enabled)
self.check_only_show.setChecked(cfg.kill_only_during_slideshow)
self.check_change_on_start.setChecked(cfg.change_wallpaper_on_start)
self.check_minimize_to_tray.setChecked(cfg.minimize_to_tray)
self.check_weather.setChecked(cfg.weather_enabled)
self.check_autostart.setChecked(controller.autostart_enabled)
```

`controller.start()` 会自动检查/创建开机自启快捷方式，然后发 `autostart_changed`；
连接要在 `start()` 之前完成（`main.py` 里 `MainWindow` 先构造，再 `start`）。

倒计时标签：

```python
from gyhd.countdown import exam_info
info = exam_info(controller.config.stage)
self.label_countdown.setText(f"距离{info.exam} {info.days} 天 · {info.target}")
```

## 6. 适配层骨架

下面假设你已经加了表里的**必需 + 建议**控件；`label_slideshow`、`label_kill_count`
这类可选标签用 `hasattr` 做了保护，没加也不会报错。

```python
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow

from gyhd.countdown import exam_info

from .main_window_ui import Ui_MainWindow


def _set_checked(widget, value: bool) -> None:
    widget.blockSignals(True)
    widget.setChecked(value)
    widget.blockSignals(False)


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self._controller = controller
        self._can_minimize_to_tray = False
        self._kill_count = 0

        self.btn_browse.clicked.connect(self._browse)
        self.btn_change.clicked.connect(controller.change_wallpaper)
        self.combo_stage.currentTextChanged.connect(self._on_stage_changed)
        self.check_guard.toggled.connect(controller.set_guard_enabled)
        self.check_only_show.toggled.connect(
            controller.set_kill_only_during_slideshow
        )
        self.check_autostart.toggled.connect(self._toggle_autostart)
        self.btn_quit.clicked.connect(QApplication.quit)

        controller.config_changed.connect(self._on_config_changed)
        controller.autostart_changed.connect(self._on_autostart_changed)
        controller.monitoring_changed.connect(self._on_monitoring)
        controller.slideshow_changed.connect(self._on_slideshow)
        controller.recorder_blocked.connect(self._on_blocked)
        controller.wallpaper_changed.connect(self._on_wallpaper_changed)
        controller.wallpaper_failed.connect(self._on_wallpaper_failed)
        controller.error.connect(self._append_log)

        self._sync_from_config()

    # ---- 状态回填 ----

    def _sync_from_config(self) -> None:
        cfg = self._controller.config
        self.lineEdit_path.setText(cfg.wallpaper_folder)

        self.combo_stage.blockSignals(True)
        self.combo_stage.setCurrentText(cfg.stage)
        self.combo_stage.blockSignals(False)

        _set_checked(self.check_guard, cfg.guard_enabled)
        _set_checked(self.check_only_show, cfg.kill_only_during_slideshow)
        _set_checked(self.check_autostart, self._controller.autostart_enabled)
        self._update_countdown()

    def _on_config_changed(self, _config) -> None:
        self._sync_from_config()

    def _update_countdown(self) -> None:
        info = exam_info(self._controller.config.stage)
        self.label_countdown.setText(
            f"距离{info.exam} {info.days} 天 · {info.target.isoformat()}"
        )

    # ---- 控件动作 ----

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "选择壁纸文件夹", self.lineEdit_path.text()
        )
        if not folder:
            return
        if self._controller.set_wallpaper_folder(folder):
            self.lineEdit_path.setText(folder)
            self._append_log(f"壁纸文件夹：{folder}")
        else:
            self._append_log("壁纸文件夹不可访问")

    def _on_stage_changed(self, stage: str) -> None:
        if stage != self._controller.config.stage:
            self._controller.set_stage(stage)
        self._update_countdown()

    def _toggle_autostart(self, enabled: bool) -> None:
        if not self._controller.set_autostart(enabled):
            self._on_autostart_changed(self._controller.autostart_enabled)

    # ---- controller 信号 ----

    def _on_monitoring(self, enabled: bool) -> None:
        _set_checked(self.check_guard, enabled)

    def _on_autostart_changed(self, enabled: bool) -> None:
        _set_checked(self.check_autostart, enabled)

    def _on_slideshow(self, active: bool) -> None:
        if hasattr(self, "label_slideshow"):
            self.label_slideshow.setText(
                "正在放映" if active else "未检测到放映"
            )

    def _on_blocked(self, name: str, pid: int) -> None:
        self._kill_count += 1
        if hasattr(self, "label_kill_count"):
            self.label_kill_count.setText(f"已拦截录屏：{self._kill_count} 次")
        self._append_log(f"已结束录屏进程：{name} (PID {pid})")

    def _on_wallpaper_changed(self, path: str) -> None:
        if hasattr(self, "label_wallpaper_status"):
            self.label_wallpaper_status.setText(f"上次更换：{path}")
        self._append_log(f"壁纸已更换：{path}")

    def _on_wallpaper_failed(self, message: str) -> None:
        if hasattr(self, "label_wallpaper_status"):
            self.label_wallpaper_status.setText(f"更换失败：{message}")
        self._append_log(f"更换失败：{message}")

    def _append_log(self, message: str) -> None:
        if hasattr(self, "plainText_log"):
            self.plainText_log.appendPlainText(message)

    # ---- main.py / 托盘需要的接口 ----

    def show_and_raise(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def set_tray_available(self, available: bool) -> None:
        self._can_minimize_to_tray = bool(available)

    def closeEvent(self, event) -> None:
        if self._can_minimize_to_tray and self._controller.config.minimize_to_tray:
            event.ignore()
            self.hide()
            return
        event.accept()
        QApplication.quit()
```

## 7. 生成与预览

```powershell
# 保存为 gyhd/ui/main_window.ui 后
python -m PyQt5.uic.pyuic gyhd\ui\main_window.ui -o gyhd\ui\main_window_ui.py
```

- 不要手改生成的 `main_window_ui.py`
- Designer 里 `Ctrl+R` 预览
- 运行 `python main.py` 看真实接线
- 报 `AttributeError: ... btn_browse` 就是 objectName 不一致

更完整的生命周期、线程规则和布局建议见 [UI_CONTRACT.md](UI_CONTRACT.md)。
