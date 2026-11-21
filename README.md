# 花都校区畅言增强工具

从 [HuaDuXiaoQuDingZhiBiZhiQieHuan](https://github.com/kuqilin/HuaDuXiaoQuDingZhiBiZhiQieHuan) 衍生出来的 Qt5 新项目，把两件事合到一个后台程序里：

1. **随机壁纸切换**：从指定文件夹随机挑一张图设为桌面壁纸，开机自动换。
2. **WPS 放映守护**：持续监测 WPS 是否正在全屏放映 PPT；放映期间一旦发现误触启动的 WPS 录屏程序（ApowerREC），就把它结束掉。

> 界面部分按你的要求留给你来做。仓库里现在有一份能跑通全部后端的**占位界面**，
> 后端接口和替换方法见 [docs/UI_CONTRACT.md](docs/UI_CONTRACT.md)。

## 功能

- 随机壁纸：支持 `.jpg` `.jpeg` `.png` `.bmp` `.gif`，默认避开当前壁纸，避免连续两次同一张
- 壁纸倒计时：选择学段（高一～高三 / 初一～初三），自动计算距离高考（6.7）或中考（6.30）天数
- 当天气温：在壁纸上写 `xx℃~xx℃`，数据来自 Open-Meteo，失败时只省略气温
- 源图不改：文字画在生成的副本上，输出到 `%LOCALAPPDATA%\...\wallpapers`
- 壁纸文件夹可在界面里选择，配置保存在 `%LOCALAPPDATA%`，不再依赖当前工作目录
- 自动部署：第一次从别处运行时，复制到 `D:\GYHD-Enhancement-Changyan` 并自动重启
- 开机自启：启动时检查“启动”文件夹，没有快捷方式就自动创建，不需要管理员权限
- 启动参数：`--startup` 不显示主界面，只换壁纸并进入后台守护；`--wallpaper-only` 只换壁纸后退出
- WPS 放映检测：识别全屏放映窗口，而不是简单地“WPS 在运行就杀”
- 录屏拦截：默认**只在 PPT 全屏放映时**结束 `ApowerREC.exe` 及其同目录辅助进程
- 演练模式：只记录“本应结束哪个进程”，不真的杀，便于在真机上验证识别是否正确
- 系统托盘：关闭窗口可最小化到托盘，托盘菜单可暂停守护、立即换壁纸
- 单实例：重复启动不会产生两个守护线程
- 文件日志：`%LOCALAPPDATA%\GYHD-Enhancement-Changyan\logs\app.log`

## 壁纸上的倒计时和气温

选中“学段”后，每次换壁纸时：

1. 高中三个学段数到各自的高考年份（6 月 7 日）：高三最近一次，高二加一年，高一加两年；
   初中同理，数到 6 月 30 日（中考）；
2. 考试当天显示“今天高考/中考”，过了考试日自动顺延到下一次；
3. 从 Open-Meteo 取当天最低/最高气温，格式固定为 `15℃~25℃`；
4. 用 Qt 把文字画在源图的**副本**上，源文件只读，不会被覆盖。

壁纸副本保存在：

```
%LOCALAPPDATA%\GYHD-Enhancement-Changyan\wallpapers\wallpaper-*.jpg
```

只保留最近 5 张，旧的自动清理。位置在右下角、任务栏上方，半透明黑底白字，不挡桌面图标。
天气接口失败（断网、超时、证书问题）时只印倒计时，不影响换壁纸。
Open-Meteo 失败会再试 vvhan 的国内接口（城市名由 `WEATHER_CITY` 控制）。

坐标默认是广州花都，换城市改 `gyhd/constants.py` 的
`WEATHER_LATITUDE` / `WEATHER_LONGITUDE`，备用接口的城市名 `WEATHER_CITY` 也一起改。

## 我们是怎么找到“那个录屏程序”的

WPS 的“录屏”不是 WPS 自己实现的，而是调用随插件分发的 **ApowerREC**。
在 WPS 12.1.0.22089 上实测/逆向得到的结论：

### 放映窗口

用临时 PPT 起放映后枚举顶层窗口，命中：

| 属性 | 实测值 |
| --- | --- |
| 进程 | `wpp.exe` |
| 窗口类 | `Qt5QWindowIcon` |
| 标题 | `WPS Presentation Slide Show - [test.pptx]` |
| 位置/大小 | `(0, 0, 1440, 960)`，正好等于整个显示器 |
| 样式 | 无边框全屏 |

所以守护的判断条件是“WPS 进程 + 放映类窗口/标题 + 全屏”，不是只看 `wpp.exe` 是否存在。
正常编辑窗口的类是 `PP12FrameClass`，标题是 `test.pptx - WPS Office`，不会被误判。

### 录屏进程

`wppmain.dll` 里能搜到这些字符串，说明放映工具栏的录屏入口会拉起 `kapower` 插件：

```
__WPP_KApowerCtrl__
app_kapower_slideshow
supportscreenrecorder
Preparing for Apower
```

插件实际落在：

```
%APPDATA%\Kingsoft\wps\addons\pool\win-i386\kapower_3.1.0.143\kapowerapp\
    ApowerREC.exe          ← 主程序
    helper32.exe / helper64.exe
    ffmpeg.exe
    SetDisplay32.exe / SetDisplay64.exe
```

`ApowerREC.exe` 的版本信息是 `ApowerREC 1.6.10.3`（Apowersoft）。

守护的匹配规则：

- 进程名包含 `apowerrec` / `kapower` / `wpsrecorder` / `wpsrecord`，或
- 可执行文件路径在 `...\kapower_*\...` 目录下，或路径里含 `apowerrec`

版本号 `3.1.0.143` 会随 WPS 升级变化，所以**匹配的是目录前缀 `kapower_` 和文件名，不写死版本号**。
同目录的 `helper64.exe`、`ffmpeg.exe` 也会被路径规则命中，避免主进程结束后辅助进程继续录。

> 已用真实的 `ApowerREC.exe 1.6.10.3` 做过一次端到端验证：
> 启动它 → `WpsGuard` 识别为录屏进程 → `TerminateProcess` → 进程消失。

## 环境要求

- Windows 10 / 11
- Python 3.10+（3.11+ 用标准库 `tomllib`；3.10 会从 requirements 安装 `tomli`）
- PyQt5 >= 5.15.11
- pywin32 >= 306（只用于创建开机自启的 `.lnk`；进程/窗口/壁纸仍然用 `ctypes` + `winreg`）

## 从源码运行

### 1. 克隆

```powershell
git clone git@github.com:kuqilin/GYHD-Enhancement-Changyan.git
cd GYHD-Enhancement-Changyan
```

### 2. 创建并激活虚拟环境

```powershell
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\activate
```

`Set-ExecutionPolicy -Scope Process` 只对当前窗口生效。Python 3.13 的部分安装包给
`Activate.ps1` 签了已经过期的短期证书，PowerShell 的 `RemoteSigned` 策略会报
“证书已被颁发者直接吊销”，所以先对当前窗口放开一次。

### 3. 安装依赖

```powershell
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 60
```

`PyQt5-Qt5` 单个 wheel 约 60 MB，直连 PyPI 容易卡在 `Collecting PyQt5`，建议用国内镜像。

### 4. 运行

```powershell
python main.py                  # 显示主界面
python main.py --startup        # 开机自启：不显示主界面，换壁纸 + 后台守护
python main.py --wallpaper-only # 只换一张壁纸后退出，不启动界面/守护
python main.py --dry-run        # 演练模式：只记录，不结束录屏进程（不会写进配置）
python main.py --debug          # 控制台 + 文件日志
```

`--startup` 和 `--minimized` 等价，都是“隐藏主窗口、保留托盘和后台守护”。
`--dry-run` 只影响本次进程，退出时不会保存；持久开关是 `config.toml` 里的 `guard_dry_run`。

如果当前目录不是项目根目录，建议用 `python D:\path\to\GYHD-Enhancement-Changyan\main.py`，
配置路径仍然是 `%LOCALAPPDATA%`，不会因为 CWD 不同而读错。

## 自动部署与开机自启

第一次从桌面、下载目录或源码目录运行时：

1. 检查 `D:\GYHD-Enhancement-Changyan` 是否已经有完整程序；
2. 没有就复制过去，然后用相同参数从 D 盘重新启动，当前进程退出；
3. 新进程启动后检查“启动”文件夹里的快捷方式，没有就创建，参数固定为 `--startup`。

自启快捷方式位置：

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\GYHD-Enhancement-Changyan.lnk
```

行为细节：

- D 盘不存在、没有写权限或复制失败：只记日志，继续从当前位置运行，不阻塞使用
- 调试时可以加 `--skip-deploy`，或设置环境变量 `GYHD_SKIP_DEPLOY=1`
- 想换安装位置：设置 `GYHD_INSTALL_DIR`，或改 `gyhd/constants.py` 的 `DEFAULT_INSTALL_DIR`
- 快捷方式由 pywin32 创建；pywin32 不可用时降级写 `HKCU\...\Run`，至少保证能自启
- 取消界面里的“开机自动启动”会把 `config.toml` 的 `autostart` 写成 `false`，
  这样下次启动就不会又自动建回来；想恢复就重新勾选

## 配置

配置文件：`%LOCALAPPDATA%\GYHD-Enhancement-Changyan\config.toml`

```toml
schema_version = 1
wallpaper_folder = 'D:\花都校区定制壁纸'
stage = '高三'
weather_enabled = true
change_wallpaper_on_start = true
guard_enabled = true
guard_interval_ms = 500
kill_only_during_slideshow = true
guard_dry_run = false
minimize_to_tray = true
autostart = true
```

路径建议用单引号（TOML literal string），这样 Windows 反斜杠不需要写成 `\\`。

> 从 0.1.2 起配置格式是 TOML。第一次启动时如果只找到旧的 `config.json`，
> 会自动迁移成 `config.toml`，并把旧文件备份为 `config.json.migrated-<时间戳>`，
> 原来的壁纸路径和开关都会保留。

| 字段 | 说明 |
| --- | --- |
| `wallpaper_folder` | 壁纸文件夹，必须存在；不存在时程序只记日志，不会静默改回默认值 |
| `stage` | 学段：`高一` `高二` `高三` `初一` `初二` `初三`；高三/初三数最近一次考试，高二/初二 +1 年，高一/初一 +2 年 |
| `weather_enabled` | 是否请求 Open-Meteo 取当天气温；`false` 时壁纸只印倒计时 |
| `change_wallpaper_on_start` | 启动时自动换一张 |
| `guard_enabled` | 是否启动后台 WPS 守护 |
| `guard_interval_ms` | 轮询间隔，限制在 200–5000 ms，默认 500 |
| `kill_only_during_slideshow` | `true`：只在放映时杀；`false`：任何时候发现录屏进程都杀 |
| `guard_dry_run` | 演练模式，只产生“检测到”日志，不调用 `TerminateProcess` |
| `minimize_to_tray` | 关闭主窗口时是否隐藏到托盘 |
| `autostart` | 是否在启动时自动确保开机自启快捷方式存在；界面取消勾选后写 `false` |

日志：`%LOCALAPPDATA%\GYHD-Enhancement-Changyan\logs\app.log`，单文件 1 MB，保留 3 份。

### 手动验证识别是否正确

先开一个 PPT 放映，再运行：

```powershell
python tools/diagnose_wps.py
```

它会打印当前 WPS 窗口、哪个窗口被判为放映、以及匹配到的录屏进程，**不会结束任何进程**。
如果放映时 `slideshow=False`，或者误触录屏后 `recorders` 为空，就说明 WPS 版本变了，
需要更新 `gyhd/constants.py` 里的匹配关键字（见“维护与适配”）。

## 界面开发（这部分留给你）

当前界面在 [`gyhd/ui/main_window.py`](gyhd/ui/main_window.py)，只是占位：
标题、壁纸文件夹选择、立即更换、守护开关、自启开关、日志框都接好了后端，
但排版和视觉没有打磨。你可以：

1. **直接改 `MainWindow`**：保留 `MainWindow(controller)` 构造签名，以及
   `show_and_raise()` / `set_tray_available(bool)` / `closeEvent`，其他随便重写。
2. **用 Qt Designer**：新建 `gyhd/ui/main_window.ui`，用 `python -m PyQt5.uic.pyuic ...` 生成，
   再在 `MainWindow.__init__` 里 `self.setupUi(self)`。完整步骤见
   [docs/UI_CONTRACT.md](docs/UI_CONTRACT.md) 的“Qt Designer 详细步骤”。
3. **换掉托盘**：`gyhd/ui/tray.py` 可以整体替换，只要 `main.py` 还能拿到
   `tray.available` 和 `tray.show()` 即可。

后端是唯一的，不要在界面里自己 new `AppController` 或 `WpsGuard`。
完整的信号/方法/配置字段说明、线程规则和建议布局见
**[docs/UI_CONTRACT.md](docs/UI_CONTRACT.md)**。

> 显示名在 `gyhd/constants.py` 的 `APP_NAME_FULL` 里，窗口标题、托盘、自启项都会跟着变。

## 测试

```powershell
python -m unittest discover -s tests -v
```

当前 76 个用例，覆盖：

- 配置默认值、TOML 往返、损坏备份、JSON→TOML 迁移、间隔限制、未知字段兼容
- 命令行 `--dry-run` 不写回配置的回归测试
- 部署复制：忽略 tests/runtime/.git/config，识别已安装目录，快捷方式参数
- 倒计时：高中/初中映射、考试当天为 0、过期顺延、非法学段兜底
- 天气 JSON 解析（Open-Meteo + vvhan 备用）、缺字段/非法值兜底
- 壁纸副本：不改源文件、生成尺寸正确、旧副本清理
- 图片枚举/排序、避开当前壁纸、系统调用失败、transform 输出
- 放映窗口判定：英文/中文标题、全屏兜底、编辑器窗口不误判、文件名含“放映”不误判
- 录屏进程判定：WPS 插件路径、独立安装的 ApowerREC、同目录 helper/ffmpeg、WPS 自身不误判
- 守护决策：只在放映时杀、关闭限制后随时杀、演练模式、结束失败、不杀自己

真实进程验证（需要你真的触发 WPS 录屏，或手动启动 ApowerREC）：

```powershell
# 1. 开一个 PPT 放映
# 2. 点 WPS 放映工具栏里的“录屏”，或直接启动 ApowerREC.exe
# 3. 看日志 / 托盘提示，ApowerREC.exe 应该在一秒内消失
Get-Content "$env:LOCALAPPDATA\GYHD-Enhancement-Changyan\logs\app.log" -Tail 20
```

## 打包

```powershell
pip install -r requirements-dev.txt
pyinstaller -F -w -i .\assets\GY_1080x1080.ico --add-data "assets;assets" --hidden-import win32com.client --name GYHD-Enhancement-Changyan .\main.py --clean
```

- `--add-data "assets;assets"`：托盘图标是运行时从 `assets/` 读的，必须一起打进去
- `--hidden-import win32com.client`：创建开机自启 `.lnk` 用，漏了会在运行时找不到模块
- `-w`：无控制台；日志仍然写到文件
- `-F`：单文件。后台常驻程序也可以用 `-D`（onedir），启动更快、被杀毒误报更少
- 打包后快捷方式会指向 exe，不再依赖 Python

产物在 `dist\GYHD-Enhancement-Changyan.exe`。

## 开机自启

程序启动时会自动检查“启动”文件夹里有没有 `GYHD-Enhancement-Changyan.lnk`，
没有就创建，参数固定为 `--startup`。位置：

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\GYHD-Enhancement-Changyan.lnk
```

`--startup` 的行为：不显示主界面，换一张壁纸，并启动托盘和后台 WPS 守护。
它和 `--minimized` 等价。想要“只换壁纸、不常驻”，用 `--wallpaper-only`。

不需要管理员权限。界面里的“开机自动启动”取消勾选后，会删除快捷方式并把
`config.toml` 的 `autostart` 写成 `false`，下次启动不会又自动建回来。

## 目录结构

```
GYHD-Enhancement-Changyan/
├─ main.py                     # 入口：命令行、QApplication、单实例、托盘
├─ gyhd/
│  ├─ constants.py             # 应用名、路径、WPS/录屏匹配关键字
│  ├─ config.py                # Config + 原子化 ConfigStore
│  ├─ controller.py            # 给 UI 的后端门面（信号/方法）
│  ├─ guard_worker.py          # QThread 包装 WpsGuard
│  ├─ wps_guard.py             # 放映判定 + 录屏进程判定 + 结束决策
│  ├─ winproc.py               # ctypes：枚举进程、TerminateProcess
│  ├─ winwindow.py             # ctypes：枚举顶层窗口、显示器矩形
│  ├─ wallpaper.py             # ctypes：SystemParametersInfoW 设置壁纸
│  ├─ wallpaper_service.py     # 选图 → 印字 → 设置壁纸
│  ├─ countdown.py             # 学段 → 高考/中考倒计时
│  ├─ weather.py               # Open-Meteo 当天气温
│  ├─ overlay.py               # Qt 在壁纸副本上画倒计时/气温
│  ├─ deployment.py            # 复制自身到 D 盘并重启
│  ├─ autostart.py             # 启动文件夹 .lnk，pywin32 创建
│  ├─ single_instance.py       # CreateMutexW
│  ├─ logging_setup.py
│  └─ ui/                      # 占位界面 + 托盘（你来改）
├─ tests/                      # 76 个 unittest
├─ tools/diagnose_wps.py       # 只读诊断：窗口/录屏进程
├─ docs/UI_CONTRACT.md         # 界面后端契约
├─ assets/GY_1080x1080.ico
├─ requirements.txt
├─ requirements-dev.txt
└─ README.md
```

## 维护与适配

WPS 更新可能改窗口标题、窗口类或录屏插件名。出现“识别不到”时，按顺序检查：

1. 运行 `python tools/diagnose_wps.py`，确认 `slideshow` 和 `recorders` 的输出。
2. 如果放映窗口的类/标题变了，改 `gyhd/constants.py`：
   - `SLIDESHOW_TITLE_MARKERS`：强关键字（`slide show` / `幻灯片放映`）
   - `SLIDESHOW_WEAK_TITLE_MARKERS`：只在放映类窗口上才认的弱关键字（`放映`）
   - `WPS_PROCESS_NAMES`：WPS 进程名
3. 如果录屏进程名/路径变了，改：
   - `RECORDER_NAME_MARKERS`
   - `RECORDER_PATH_MARKERS`
4. 改完跑 `python -m unittest discover -s tests -v`。

## 常见问题

**Q：杀进程会不会把 WPS 弄崩？**
只结束匹配 `ApowerREC` / `kapower` / `wpsrecorder` 的进程，WPS 的 `wps.exe`、`wpp.exe` 不在匹配列表里；
录制程序被结束后，WPS 可能弹一个“录屏程序已停止工作”的提示，属于预期现象。

**Q：为什么不是“阻止启动”，而是“启动后再杀”？**
不做驱动/Hook、不申请管理员权限的前提下，用户态程序无法阻止另一个进程创建；
轮询 + 结束是权限要求最低、最稳的做法。ApowerREC 启动后通常有 3 秒倒计时，
500 ms 的轮询一般能在真正开始录制前结束它，但**不保证 0 帧泄露**。

**Q：我正常用 ApowerREC 录别的内容，会被误杀吗？**
默认 `kill_only_during_slideshow=true`，只有 WPS 处于全屏放映时才杀；
不在放映时录屏不受影响。放映期间如果你确实要录，先取消勾选“启用后台守护”。

**Q：没加 `--dry-run`，日志还是显示“演练模式”？**
0.1.0 有一个 bug：`--dry-run` 在退出时被 `shutdown()` 保存进了配置。
0.1.1 已修好，并且同一 PID 不再每 500 ms 刷一行日志。把
`%LOCALAPPDATA%\GYHD-Enhancement-Changyan\config.toml` 里的 `guard_dry_run` 改成
`false` 即可。

**Q：旧的 config.json 还在，会读哪个？**
优先读 `config.toml`。只有找不到 TOML 时才会读 `config.json` 并自动迁移，
迁移成功后旧文件会改名成 `config.json.migrated-<时间戳>`。

**Q：第一次运行没有复制到 D 盘？**
看日志里的 `部署到 ... 失败`。常见原因：D 盘不存在、D 盘根目录没有写权限、
`D:\GYHD-Enhancement-Changyan` 已经存在。可以用环境变量
`GYHD_INSTALL_DIR` 换目标目录，或加 `--skip-deploy` 跳过部署。

**Q：启动文件夹里没有快捷方式 / 开机没自启？**
先确认 `config.toml` 里 `autostart = true`，然后手动跑：

```powershell
python -c "from gyhd import autostart; print(autostart.ensure_shortcut()); print(autostart.shortcut_path())"
```

如果提示 pywin32 未安装，执行 `pip install -r requirements.txt`。旧版本的
`HKCU\...\Run` 会被自动清理，避免和快捷方式重复启动。

**Q：`--startup` 为什么还保留了托盘和守护？**
因为 WPS 录屏守护需要常驻，主窗口不显示但进程要继续跑。如果你只想要
“换完壁纸就退出、不常驻”，把快捷方式参数改成 `--wallpaper-only` 即可。

**Q：WPS 以管理员身份运行，守护杀不掉？**
Windows 不允许低完整性进程结束高完整性进程。让本程序和 WPS 使用相同权限运行；
如果 WPS 是管理员启动的，本程序也要以管理员启动。

**Q：`.\venv\Scripts\activate` 报“证书已被颁发者直接吊销”？**
见上面“从源码运行 → 2. 创建并激活虚拟环境”。这是 Python 安装包签名证书过期，不是本项目的问题。

**Q：`pip install` 卡在 `Collecting PyQt5`？**
换清华镜像并加 `--timeout 60`，见“从源码运行 → 3. 安装依赖”。

**Q：开机后壁纸没变？**
先看日志里的 `更换壁纸失败`；常见原因是 `wallpaper_folder` 不存在或里面没有支持的图片。
程序不会像旧版那样在运行时把用户配置静默改回默认值。

**Q：设置页保存了，壁纸没立即变？**
“保存文件夹”只保存配置；点“立即更换”才会马上换。开机时的自动更换由 `change_wallpaper_on_start` 控制。

## 已知限制

- 只支持 Windows；`ctypes` 直接调用 `user32` / `psapi` / `kernel32`。
- 自动部署只在 `D:\GYHD-Enhancement-Changyan` 缺失时复制；D 盘已有旧版本不会自动覆盖，
  需要手动删掉旧目录再运行，或用 `GYHD_INSTALL_DIR` 换一个目标目录。
- 从源码运行时，D 盘副本仍依赖当前 Python 环境；打包成 exe 后自启才完全独立。
- 天气坐标固定为广州花都；换城市改 `WEATHER_LATITUDE/LONGITUDE` 和 `WEATHER_CITY`。
  断网或接口超时时壁纸只印倒计时，不印气温。
- 倒计时按学段推算考试年份（高三最近一次，高二 +1 年，高一 +2 年；初中同理），
  不读取学生实际入学信息；考试当天为 0 天。
- 放映判定基于 WPS 12.1 的实测特征，WPS 大版本升级后可能需要更新关键字（见“维护与适配”）。
- 录屏拦截是“启动后结束”，不是内核级阻止；对极短的录制仍可能截到开头几帧。
- 多显示器时，只要任意一个 WPS 放映窗口命中，就认为在放映；没有区分“演讲者视图”和“观众视图”。

## 许可

[MIT License](LICENSE)
