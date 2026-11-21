# -*- coding: utf-8 -*-
"""花都校区畅言增强工具入口。

阶段：
    1. 首次从其他位置运行时，把自身复制到 D:\\GYHD-Enhancement-Changyan 并重启；
    2. 检查/创建“启动”文件夹里的开机自启快捷方式；
    3. 正常启动 Qt 界面、托盘、壁纸和 WPS 守护。

常用命令：
    python main.py                 # 显示主界面
    python main.py --startup       # 开机自启：不显示主界面，换壁纸 + 后台守护
    python main.py --wallpaper-only  # 只换一张壁纸后退出
    python main.py --dry-run       # 演练模式，只记录不结束录屏进程
    python main.py --debug         # 控制台 + 文件日志
"""

from __future__ import annotations

import argparse
import logging
import sys

try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QGuiApplication, QIcon
    from PyQt5.QtWidgets import QApplication, QMessageBox
except ImportError:
    print(
        "缺少 PyQt5。请在项目目录执行：\n"
        "    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple",
        file=sys.stderr,
    )
    raise SystemExit(1)

from gyhd import deployment
from gyhd.config import Config, ConfigStore
from gyhd.constants import APP_NAME, APP_NAME_FULL, APP_VERSION, ORG_NAME, icon_path
from gyhd.controller import AppController
from gyhd.logging_setup import setup_logging
from gyhd.single_instance import SingleInstance
from gyhd.ui.main_window import MainWindow
from gyhd.ui.tray import TrayIcon
from gyhd.wallpaper import WallpaperError
from gyhd.wallpaper_service import perform_wallpaper_change

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=APP_NAME_FULL)
    parser.add_argument(
        "--startup",
        "--autostart",
        dest="startup",
        action="store_true",
        help="开机自启：不显示主界面，换壁纸并进入后台守护（快捷方式使用）",
    )
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="只显示托盘图标（兼容旧参数，等同 --startup）",
    )
    parser.add_argument(
        "--wallpaper-only",
        action="store_true",
        help="只换一张壁纸后退出，不启动界面、托盘和守护",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="演练模式：只记录本应结束的录屏进程，不真正结束",
    )
    parser.add_argument(
        "--skip-deploy",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--debug", action="store_true", help="输出调试日志")
    parser.add_argument(
        "--version",
        action="version",
        version=f"{APP_NAME} {APP_VERSION}",
    )
    return parser


def _wallpaper_only() -> int:
    """不创建主窗口，只换一张壁纸后退出。"""
    store = ConfigStore()
    try:
        config = store.load()
    except Exception:  # noqa: BLE001
        logger.exception("读取配置失败，使用默认配置换壁纸")
        config = Config().normalized()

    # 文字绘制需要 QGuiApplication 的字体引擎。
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([sys.argv[0]])

    try:
        path = perform_wallpaper_change(config)
    except WallpaperError as exc:
        logger.error("只换壁纸失败：%s", exc)
        return 1
    logger.info("只换壁纸完成：%s", path)
    return 0


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(raw_args)
    setup_logging(args.debug)
    logger.info(
        "启动 %s %s（frozen=%s, root=%s）",
        APP_NAME,
        APP_VERSION,
        deployment.is_frozen(),
        deployment.current_root(),
    )

    if args.wallpaper_only:
        return _wallpaper_only()

    # 部署必须发生在 QApplication / 单实例锁之前：复制成功后当前进程直接退出。
    if not args.skip_deploy and deployment.deploy_and_relaunch(raw_args):
        return 0

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication([sys.argv[0]])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setQuitOnLastWindowClosed(False)
    if icon_path().is_file():
        app.setWindowIcon(QIcon(str(icon_path())))

    startup_mode = args.startup or args.minimized

    instance = SingleInstance()
    if instance.already_running:
        logger.info("检测到已有实例，退出本次启动")
        if not startup_mode:
            QMessageBox.information(
                None,
                APP_NAME,
                "程序已经在运行，请查看系统托盘（或任务栏右下角）。",
            )
        instance.close()
        return 0

    try:
        # --dry-run 通过 override 传入，不修改、也不保存 config.guard_dry_run。
        controller = AppController(ConfigStore(), dry_run_override=args.dry_run)

        window = MainWindow(controller)
        tray = TrayIcon(controller, window)
        window.set_tray_available(tray.available)
        tray.show()
        controller.start()

        if not startup_mode:
            window.show()
        elif not tray.available:
            logger.warning("系统托盘不可用，--startup 只运行后台守护，不显示主界面")
    except Exception:
        logger.exception("启动失败")
        instance.close()
        raise

    app.aboutToQuit.connect(controller.shutdown)
    exit_code = app.exec_()
    instance.close()
    logger.info("程序退出，exit_code=%s", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
