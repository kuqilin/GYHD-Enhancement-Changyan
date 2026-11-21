# -*- coding: utf-8 -*-
"""日志初始化。"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from .constants import log_dir


def setup_logging(debug: bool = False) -> None:
    root = logging.getLogger()
    if getattr(root, "_gyhd_configured", False):
        return

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        log_dir().mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir() / "app.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        # 日志目录不可写时不能影响主程序启动。
        pass

    if debug and sys.stderr is not None:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)

    root.setLevel(logging.DEBUG if debug else logging.INFO)
    root._gyhd_configured = True  # type: ignore[attr-defined]
