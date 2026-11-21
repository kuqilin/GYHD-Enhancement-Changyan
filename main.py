# -*- coding: utf-8 -*-
"""GYHD 增强工具（长焰）入口。

常用命令：
    python main.py                # 显示主界面
    python main.py --minimized    # 只留托盘（开机自启用）
    python main.py --dry-run      # 演练模式，只记录不结束录屏进程
    python main.py --debug        # 控制台 + 文件日志
"""

from __future__ import annotations

import argparse
import logging
import sys

try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QIcon
    from PyQt5.QtWidgets import QApplication, QMessageBox
except ImportError:
    print(
        "缺少 PyQt5。请在项目目录执行：\n"
        "    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple",
        file=sys.stderr,
    )
    raise SystemExit(1)

from gyhd.config import ConfigStore
from gyhd.constants import APP_NAME, APP_NAME_FULL, APP_VERSION, ORG_NAME, icon_path
from gyhd.controller import AppController
from gyhd.logging_setup import setup_logging
from gyhd.single_instance import SingleInstance
from gyhd.ui.main_window import MainWindow
from gyhd.ui.tray import TrayIcon

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=APP_NAME_FULL)
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="启动后只显示托盘图标（开机自启使用）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="演练模式：只记录本应结束的录屏进程，不真正结束",
    )
    parser.add_argument("--debug", action="store_true", help="输出调试日志")
    parser.add_argument(
        "--version",
        action="version",
        version=f"{APP_NAME} {APP_VERSION}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    setup_logging(args.debug)
    logger.info(
        "启动 %s %s（frozen=%s）", APP_NAME, APP_VERSION, getattr(sys, "frozen", False)
    )

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication([sys.argv[0]])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setQuitOnLastWindowClosed(False)
    if icon_path().is_file():
        app.setWindowIcon(QIcon(str(icon_path())))

    instance = SingleInstance()
    if instance.already_running:
        logger.info("检测到已有实例，退出本次启动")
        if not args.minimized:
            QMessageBox.information(
                None,
                APP_NAME,
                "程序已经在运行，请查看系统托盘（或任务栏右下角）。",
            )
        instance.close()
        return 0

    try:
        controller = AppController(ConfigStore())
        if args.dry_run:
            # 只改内存中的配置，不写回 config.json
            controller.config.guard_dry_run = True
            logger.info("已启用演练模式：不会真正结束录屏进程")

        window = MainWindow(controller)
        tray = TrayIcon(controller, window)
        window.set_tray_available(tray.available)
        tray.show()
        controller.start()

        if not args.minimized or not tray.available:
            window.show()
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
