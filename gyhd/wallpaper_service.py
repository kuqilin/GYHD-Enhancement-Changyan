# -*- coding: utf-8 -*-
"""一次完整的换壁纸流程：选图 → 印倒计时/气温 → 设置壁纸。"""

from __future__ import annotations

import logging
from pathlib import Path

from .config import Config
from .countdown import exam_info
from .overlay import cleanup_generated, render_wallpaper
from .wallpaper import change_to_random
from .weather import get_today_temperature

logger = logging.getLogger(__name__)


def perform_wallpaper_change(
    config: Config,
    *,
    spi=None,
    rng=None,
) -> Path:
    """Controller 和 ``--wallpaper-only`` 共用这一条路径。"""
    info = exam_info(config.stage)
    weather_loaded = False
    temperature = None

    def decorate(source: Path) -> Path:
        nonlocal weather_loaded, temperature
        if not weather_loaded:
            if config.weather_enabled:
                temperature = get_today_temperature()
            weather_loaded = True
        try:
            return render_wallpaper(
                source,
                stage=info.stage,
                exam=info.exam,
                days=info.days,
                temperature=temperature,
            )
        except Exception:  # noqa: BLE001 - 文字失败也要能换壁纸
            logger.exception("生成带文字的壁纸失败，退回原图")
            return Path(source)

    path = change_to_random(
        config.wallpaper_folder,
        spi=spi,
        rng=rng,
        transform=decorate,
    )
    cleanup_generated()
    return path
