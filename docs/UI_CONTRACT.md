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
controller.start()          # 只调用一次
app.aboutToQuit.connect(controller.shutdown)
app.exec_()
```

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
| `autostart_changed` | `bool` | 开机自启开关成功改变 |
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
| `set_autostart(bool)` | `bool` | 写/删 HKCU Run 项；失败发 `error` 并返回 `False` |

只读属性：

- `controller.config`：当前 `Config`，**不要直接改字段**，用上面的 setter 才会保存并通知。
- `controller.autostart_enabled`：读注册表的真实状态。
- `controller.monitoring`：守护线程是否在运行。
- `controller.dry_run_active`：本次运行是否演练模式（命令行 `--dry-run` 优先于配置；
  命令行覆盖不会写回 `config.json`）。

## 4. 配置字段

见 README 的“配置”表。界面常用的只有：

```python
config.wallpaper_folder
config.change_wallpaper_on_start
config.guard_enabled
config.kill_only_during_slideshow
config.guard_dry_run
config.minimize_to_tray
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

### 方式 B：Qt Designer + pyuic5

```powershell
pyuic5 main_window.ui -o gyhd/ui/main_window_ui.py
```

然后：

```python
from .main_window_ui import Ui_MainWindow

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self._controller = controller
        # 连接控件信号到 controller / 本地槽
```

建议给控件起这些 objectName（不是后端强制，只是方便对应）：

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
┌─ GYHD 增强工具 ─────────────────────────────┐
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
