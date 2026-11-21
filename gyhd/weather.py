# -*- coding: utf-8 -*-
"""当天最低/最高气温，来自 Open-Meteo（免费、无需 API key）。

失败时返回 None，壁纸上就只印倒计时，不影响换壁纸。
坐标默认是广州花都，换城市改 ``constants.WEATHER_LATITUDE/LONGITUDE``。
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .constants import (
    WEATHER_CITY,
    WEATHER_LATITUDE,
    WEATHER_LONGITUDE,
    WEATHER_TIMEZONE,
    app_data_dir,
)

logger = logging.getLogger(__name__)

API_URL = "https://api.open-meteo.com/v1/forecast"
# 国内备用接口，返回 low/high 字符串；Open-Meteo 失败时再试。
FALLBACK_API_URL = "https://api.vvhan.com/api/weather"
REQUEST_TIMEOUT = 2.5
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


@dataclass(frozen=True)
class Temperature:
    low: int
    high: int

    @property
    def text(self) -> str:
        return f"{self.low}℃~{self.high}℃"


def cache_path() -> Path:
    return app_data_dir() / "weather-cache.json"


def parse_open_meteo(payload: object) -> Temperature | None:
    if not isinstance(payload, dict):
        return None
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        return None
    lows = daily.get("temperature_2m_min")
    highs = daily.get("temperature_2m_max")
    if not isinstance(lows, list) or not isinstance(highs, list):
        return None
    if not lows or not highs:
        return None

    try:
        low = int(round(float(lows[0])))
        high = int(round(float(highs[0])))
    except (TypeError, ValueError, IndexError):
        return None

    if low > high:
        low, high = high, low
    if not (-60 <= low <= 60 and -60 <= high <= 60):
        return None
    return Temperature(low=low, high=high)


def _sanitize(low: int, high: int) -> Temperature | None:
    if low > high:
        low, high = high, low
    if not (-60 <= low <= 60 and -60 <= high <= 60):
        return None
    return Temperature(low=low, high=high)


def parse_vvhan(payload: object) -> Temperature | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        data = payload
    low_text = data.get("low")
    high_text = data.get("high")
    if low_text is None or high_text is None:
        return None
    low_match = _NUMBER.search(str(low_text))
    high_match = _NUMBER.search(str(high_text))
    if not low_match or not high_match:
        return None
    try:
        return _sanitize(int(round(float(low_match.group()))), int(round(float(high_match.group()))))
    except ValueError:
        return None


def _get_json(url: str, timeout: float) -> object | None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "GYHD-Enhancement-Changyan/0.3"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - 天气不是关键路径
        logger.info("天气接口失败：%s", exc)
        return None


def _open_meteo_url() -> str:
    params = urllib.parse.urlencode(
        {
            "latitude": WEATHER_LATITUDE,
            "longitude": WEATHER_LONGITUDE,
            "daily": "temperature_2m_min,temperature_2m_max",
            "timezone": WEATHER_TIMEZONE,
            "forecast_days": 1,
        }
    )
    return f"{API_URL}?{params}"


def _fallback_url() -> str:
    params = urllib.parse.urlencode({"city": WEATHER_CITY})
    return f"{FALLBACK_API_URL}?{params}"


def fetch_today_temperature(timeout: float = REQUEST_TIMEOUT) -> Temperature | None:
    temperature = parse_open_meteo(_get_json(_open_meteo_url(), timeout))
    if temperature is None:
        temperature = parse_vvhan(_get_json(_fallback_url(), timeout))
    if temperature is not None:
        logger.info("今日气温：%s", temperature.text)
    return temperature


def _read_cache() -> tuple[str, Temperature] | None:
    path = cache_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        day = str(data["date"])
        low = int(data["low"])
        high = int(data["high"])
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
    return day, Temperature(low=low, high=high)


def _write_cache(temperature: Temperature) -> None:
    path = cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "date": date.today().isoformat(),
                    "low": temperature.low,
                    "high": temperature.high,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        logger.debug("写入气温缓存失败", exc_info=True)


def get_today_temperature(*, force: bool = False) -> Temperature | None:
    """优先读当天缓存；没有缓存或 force=True 时请求网络。"""
    today = date.today().isoformat()
    if not force:
        cached = _read_cache()
        if cached is not None and cached[0] == today:
            return cached[1]

    temperature = fetch_today_temperature()
    if temperature is not None:
        _write_cache(temperature)
    return temperature
