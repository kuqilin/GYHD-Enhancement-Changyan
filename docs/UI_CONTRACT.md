# 界面后端契约

这份文档给负责 Qt 界面的你。目标是：**界面随便改，后端只通过 `AppController` 交互。**

## 1. 启动与退出

`main.py` 已经处理好生命周期，界面不需要自己创建控制器：

```python
controller = AppController()
window = MainWindow(controller)
tray = TrayIcon(controller, window)
window.set_tray_available(tray.available)
tray.show()
controller.start()          # 只调用一次；会按 config.autostart 自动补快捷方式
app.aboutToQuit.connect(controller.shutdown)
app.exec_()
```

`main.py` 还负责部署和启动参数：

- 第一次从别处运行：复制到 `D:\GYHD-Enhancement-Changyan` 并重启
- `--startup` / `--minimized`：不显示主窗口，换壁纸 + 后台守护 + 托盘
- `--wallpaper-only`：只换壁纸后退出
- `--skip-deploy`：调试时跳过 D 盘复制

重写界面时保留：

- `MainWindow(controller)` 构造签名
- `show_and_raise()`：托盘“显示主界面”会调用
- `set_tray_available(bool)`：告诉窗口能不能最小化到托盘
- `closeEvent`：可选，但建议保留“关闭时隐藏到托盘”的行为
- `main.py` 里 `MainWindow` 的导入路径不要改，或者同步修改 `main.py`

不要在界面里 `new AppController()` / `new WpsGuard()` / 自己起线程；重复创建会产生多个守护。

## 2. 信号

| 信号 | 参数 | 触发时机 |
| --- | --- | --- |
| `wallpaper_changed` | `str` 图片路径 | 壁纸设置成功 |
| `wallpaper_failed` | `str` 错误信息 | 文件夹不存在、没图片、SPI 返回失败 |
| `config_changed` | `Config` 对象 | 任何配置项被保存后 |
| `slideshow_changed` | `bool` | WPS 进入/退出全屏放映 |
| `wps_running_changed` | `bool` | WPS 进程出现/消失 |
| `recorder_blocked` | `str` 进程名, `int` PID | 真实结束了一个录屏进程 |
| `recorder_detected` | `str` 进程名, `int` PID | 演练模式：检测到但没结束 |
| `monitoring_changed` | `bool` | 守护线程启动/暂停 |
| `autostart_changed` | `bool` | 开机自启快捷方式存在状态变化（包括启动时自动创建） |
| `error` | `str` | 非致命错误（写配置失败、结束进程失败、轮询异常） |

约定：

- 信号可能从后台线程发出，Qt 会自动排队到界面线程；槽函数里不要做耗时操作。
- `wallpaper_failed` 不弹窗，界面自己决定是显示在状态栏还是弹 `QMessageBox`。
- `error` 可能重复，建议只追加到日志框，不要每次弹窗。
- `recorder_blocked` 的进程名可能是 `ApowerREC.exe` 或 `helper64.exe`，直接展示即可。

## 3. 方法

| 方法 | 返回 | 说明 |
| --- | --- | --- |
| `start()` | `None` | 由 `main.py` 调用一次；会按配置换壁纸并启动守护 |
| `shutdown()` | `None` | 已连接到 `aboutToQuit`，停线程并保存配置 |
| `change_wallpaper()` | `str \| None` | 立即随机换一张；失败返回 `None` 并发出 `wallpaper_failed` |
| `set_wallpaper_folder(path)` | `bool` | 只保存路径，不立即换壁纸；目录不存在返回 `False` |
| `set_change_wallpaper_on_start(bool)` | `None` | 保存配置 |
| `set_minimize_to_tray(bool)` | `None` | 保存配置 |
| `set_guard_enabled(bool)` | `None` | 保存配置并启动/停止守护线程 |
| `set_kill_only_during_slideshow(bool)` | `None` | 保存配置；守护运行中会重启线程生效 |
| `set_guard_dry_run(bool)` | `None` | 持久化演练模式开关（命令行 `--dry-run` 不走这里） |
| `set_autostart(bool)` | `bool` | 创建/删除“启动”文件夹快捷方式，并更新 `config.autostart`；失败发 `error` 并返回 `False` |

只读属性：

- `controller.config`：当前 `Config`，**不要直接改字段**，用上面的 setter 才会保存并通知。
- `controller.autostart_enabled`：读注册表的真实状态。
- `controller.monitoring`：守护线程是否在运行。
- `controller.dry_run_active`：本次运行是否演练模式（命令行 `--dry-run` 优先于配置；
  命令行覆盖不会写回 `config.toml`）。

## 4. 配置字段

见 README 的“配置”表。界面常用的只有：

```python
config.wallpaper_folder
config.change_wallpaper_on_start
config.guard_enabled
config.kill_only_during_slideshow
config.guard_dry_run
config.minimize_to_tray
config.autostart
```

## 5. 线程规则

- `AppController` 的所有方法都在界面线程调用。
- `WpsGuard` 在 `GuardWorker(QThread)` 里每 `guard_interval_ms` 轮询一次；界面不要直接调它。
- 换壁纸是同步的 `SystemParametersInfoW`，通常几毫秒；如果壁纸文件夹特别大（几万张），
  列表扫描可能卡一下，建议后续把 `change_wallpaper` 放进 `QThreadPool`，但当前实现没这么做。
- 不要在槽函数里 `worker.stop()` 等 5 秒；`shutdown()` 已经处理。

## 6. 重写界面的两种方式

### 方式 A：直接改代码（最快）

改 `gyhd/ui/main_window.py` 的 `_build_ui()` 和 `_connect_signals()`，保留 `__init__` 里的
`self._controller = controller`。后端信号已经连好，照抄 `_on_*` 槽即可。

### 方式 B：Qt Designer + pyuic5（适合慢慢调外观）

#### B1. 安装 Qt Designer

PyQt5 的 wheel 只带运行时，不含 Designer。推荐只装 Qt 工具包，避免把 PyQt5 降级：

```powershell
pip install "qt5-applications==5.15.2.2.3" --no-deps -i https://pypi.tuna.tsinghua.edu.cn/simple
python -c "import qt5_applications, pathlib; print(pathlib.Path(qt5_applications.__file__).parent / 'Qt' / 'bin' / 'designer.exe')"
```

把打印出来的 `designer.exe` 双击打开。如果 `qt5-applications` 装不上，再用
`pip install pyqt5-tools`（它可能把 PyQt5 降到 5.15.9，装完执行
`pip install --force-reinstall "PyQt5==5.15.11"` 升回来）。Designer 一般在：

```
venv\Lib\site-packages\qt5_applications\Qt\bin\designer.exe
```

#### B2. 新建/保存 .ui

Designer → File → New → Main Window → Create。先放一个 `QWidget` 作为 central widget，
或者直接用 Designer 生成的 `centralwidget`。保存为：

```
gyhd/ui/main_window.ui
```

#### B3. 拖控件、设 objectName

左侧 Widget Box 拖 `QLabel` / `QLineEdit` / `QPushButton` / `QCheckBox` / `QGroupBox` /
`QPlainTextEdit`；选中同级控件后用 Layout → Lay Out Horizontally/Vertically 排布局。
右侧 Property Editor 里改 `objectName`（不是 `text`），推荐名字见下面 B7。

#### B4. 生成 Python

在项目根目录执行（用相对路径，生成文件的头注释才不会写死绝对路径）：

```powershell
python -m PyQt5.uic.pyuic gyhd\ui\main_window.ui -o gyhd\ui\main_window_ui.py
```

也可以直接用 PyQt5 自带的 `pyuic5.exe`：

```powershell
.\venv\Scripts\pyuic5.exe gyhd\ui\main_window.ui -o gyhd\ui\main_window_ui.py
```

加 `-x` 会多生成一个可单独预览的 `__main__` 块。**不要手改 `main_window_ui.py`**，
下次重新生成会覆盖；要改就改 `.ui`。

#### B5. 接线

当前 `gyhd/ui/main_window.py` 是手写界面。用 Designer 时，把它替换成适配层，
但保留 `MainWindow(controller)`、`show_and_raise()`、`set_tray_available()`、
`closeEvent()` 这几个 `main.py` / 托盘会调用的接口：

```python
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow

from .main_window_ui import Ui_MainWindow


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self._controller = controller
        self._can_minimize_to_tray = False

        self.btn_browse.clicked.connect(self._browse)
        self.btn_change.clicked.connect(controller.change_wallpaper)
        self.check_guard.toggled.connect(controller.set_guard_enabled)
        self.check_only_show.toggled.connect(
            controller.set_kill_only_during_slideshow
        )
        self.check_autostart.toggled.connect(controller.set_autostart)
        self.btn_quit.clicked.connect(QApplication.quit)

        controller.wallpaper_changed.connect(
            lambda path: self.plainText_log.appendPlainText(path)
        )
        controller.slideshow_changed.connect(self._on_slideshow)

    def _on_slideshow(self, active: bool) -> None:
        self.label_slideshow.setText("正在放映" if active else "未检测到放映")

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择壁纸文件夹")
        if folder:
            self._controller.set_wallpaper_folder(folder)

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

注意：

- 从 config 回填勾选框时先 `widget.blockSignals(True)`，设完再放开，否则 `setChecked()`
  会触发 `toggled`，把配置又写一遍。
- `set_autostart` 返回 `bool`，失败时要恢复勾选状态。
- 上面只是最小示例，日志、错误提示、拦截次数可以照 `main_window.py` 里的 `_on_*` 槽补。

#### B6. 预览与排错

- Designer 内 `Ctrl+R` 预览。
- 生成后运行 `python main.py`；如果报 `AttributeError: 'MainWindow' object has no attribute 'btn_browse'`，
  说明 Designer 里的 objectName 和代码不一致。
- 如果报 `ModuleNotFoundError: No module named 'main_window_ui'`，检查 `pyuic5` 输出路径和
  `from .main_window_ui import` 的相对导入。
- 控件拖不进布局时，先选中容器，再点 Layout 按钮；不要用绝对坐标。
- 自定义字体不会跟着仓库走，换机器会回退；要么用系统字体，要么用
  `QFontDatabase.addApplicationFont()` 打包字体。

#### B7. 推荐 objectName

| 控件 | 建议 objectName | 连接 |
| --- | --- | --- |
| 壁纸路径 | `lineEdit_path` | `controller.config.wallpaper_folder` |
| 浏览按钮 | `btn_browse` | `QFileDialog.getExistingDirectory` + `set_wallpaper_folder` |
| 立即更换 | `btn_change` | `controller.change_wallpaper` |
| 守护开关 | `check_guard` | `controller.set_guard_enabled` |
| 只在放映时 | `check_only_show` | `controller.set_kill_only_during_slideshow` |
| 开机自启 | `check_autostart` | `controller.set_autostart` |
| 放映状态 | `label_slideshow` | `slideshow_changed` |
| 拦截次数 | `label_kill_count` | 累加 `recorder_blocked` |
| 日志框 | `plainText_log` | 追加所有信号 |
| 退出 | `btn_quit` | `QApplication.quit` |

## 7. 建议布局

```
┌─ 花都校区畅言增强工具 ───────────────────────┐
│  随机壁纸 · WPS 放映时结束误触录屏            │
│                                              │
│  ┌ 桌面壁纸 ──────────────────────────────┐  │
│  │ [D:\花都校区定制壁纸        ] [浏览] [换]│  │
│  │ 上次更换：23:10   D:\...\01.jpg          │  │
│  └─────────────────────────────────────────┘  │
│  ┌ WPS 放映守护 ──────────────────────────┐  │
│  │ ☑ 启用后台守护                          │  │
│  │ ☑ 只在 PPT 全屏放映时拦截               │  │
│  │ ● 正在放映 PPT，守护已生效              │  │
│  │ 已拦截录屏：2 次                        │  │
│  └─────────────────────────────────────────┘  │
│  ┌ 行为 ──────────────────────────────────┐  │
│  │ ☑ 启动时自动换壁纸  ☑ 开机自启          │  │
│  │ ☑ 关闭窗口时最小化到托盘                 │  │
│  └─────────────────────────────────────────┘  │
│  ┌ 日志 ──────────────────────────────────┐  │
│  │ [23:10:01] 壁纸已更换：...              │  │
│  └─────────────────────────────────────────┘  │
│                          [隐藏到托盘] [退出]  │
└──────────────────────────────────────────────┘
```

## 8. 本地调试

没有 WPS 放映也可以测界面：

```powershell
python main.py --debug
```

只测界面、不碰真实壁纸：

```python
# 在 Python 交互环境里
from gyhd.config import Config, ConfigStore
store = ConfigStore()
cfg = store.load()
cfg.change_wallpaper_on_start = False
cfg.guard_enabled = False
store.save(cfg)
```

或者用 `--dry-run` 只演练录屏识别，不会真的杀进程。

## 9. 如果后端要改

- 放映/录屏判定：`gyhd/wps_guard.py` + `gyhd/constants.py`
- 进程/窗口 API：`gyhd/winproc.py`、`gyhd/winwindow.py`
- 壁纸：`gyhd/wallpaper.py`
- 配置：`gyhd/config.py`
- 给界面的门面：`gyhd/controller.py`

改完跑：

```powershell
python -m unittest discover -s tests -v
```
