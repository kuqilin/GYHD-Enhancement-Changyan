# -*- coding: utf-8 -*-
"""配置模型与原子化 TOML 读写。

配置文件默认位于 ``%LOCALAPPDATA%\\GYHD-Enhancement-Changyan\\config.toml``。
这里刻意不依赖当前工作目录（CWD），避免旧项目里“设置页改了但开机不生效”的问题。

首次读取时如果只找到旧版 ``config.json``，会自动迁移成 TOML，并把旧文件备份为
``config.json.migrated-<时间戳>``，不会丢配置。
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

from .constants import DEFAULT_WALLPAPER_FOLDER, config_path

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
MIN_GUARD_INTERVAL_MS = 200
MAX_GUARD_INTERVAL_MS = 5000


def _as_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _as_str(value: Any, default: str) -> str:
    return value if isinstance(value, str) else default


@dataclass
class Config:
    """应用配置。字段名会直接写进 TOML，改动时注意兼容旧配置。"""

    wallpaper_folder: str = DEFAULT_WALLPAPER_FOLDER
    change_wallpaper_on_start: bool = True
    guard_enabled: bool = True
    guard_interval_ms: int = 500
    kill_only_during_slideshow: bool = True
    # 演练模式：只记录“本应结束哪个进程”，不真的调用 TerminateProcess。
    guard_dry_run: bool = False
    minimize_to_tray: bool = True

    def normalized(self) -> "Config":
        folder = (self.wallpaper_folder or "").strip() or DEFAULT_WALLPAPER_FOLDER
        try:
            interval = int(self.guard_interval_ms)
        except (TypeError, ValueError):
            interval = 500
        interval = max(MIN_GUARD_INTERVAL_MS, min(MAX_GUARD_INTERVAL_MS, interval))
        return replace(
            self,
            wallpaper_folder=folder,
            guard_interval_ms=interval,
            change_wallpaper_on_start=bool(self.change_wallpaper_on_start),
            guard_enabled=bool(self.guard_enabled),
            kill_only_during_slideshow=bool(self.kill_only_during_slideshow),
            guard_dry_run=bool(self.guard_dry_run),
            minimize_to_tray=bool(self.minimize_to_tray),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "wallpaper_folder": self.wallpaper_folder,
            "change_wallpaper_on_start": self.change_wallpaper_on_start,
            "guard_enabled": self.guard_enabled,
            "guard_interval_ms": self.guard_interval_ms,
            "kill_only_during_slideshow": self.kill_only_during_slideshow,
            "guard_dry_run": self.guard_dry_run,
            "minimize_to_tray": self.minimize_to_tray,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "Config":
        if not isinstance(data, dict):
            return cls()
        return cls(
            wallpaper_folder=_as_str(
                data.get("wallpaper_folder"), DEFAULT_WALLPAPER_FOLDER
            ),
            change_wallpaper_on_start=_as_bool(
                data.get("change_wallpaper_on_start"), True
            ),
            guard_enabled=_as_bool(data.get("guard_enabled"), True),
            guard_interval_ms=data.get("guard_interval_ms", 500)
            if isinstance(data.get("guard_interval_ms"), int)
            else 500,
            kill_only_during_slideshow=_as_bool(
                data.get("kill_only_during_slideshow"), True
            ),
            guard_dry_run=_as_bool(data.get("guard_dry_run"), False),
            minimize_to_tray=_as_bool(data.get("minimize_to_tray"), True),
        )


def _toml_string(value: str) -> str:
    """JSON 字符串转义是 TOML basic string 的子集，可直接复用。"""
    return json.dumps(value, ensure_ascii=False)


def dump_toml(config: Config) -> str:
    """只序列化当前这些扁平字段，不引入额外依赖。"""
    lines = [
        "# GYHD 增强工具配置（TOML）",
        "# 修改后重启程序生效；程序退出时也会回写这个文件。",
        "",
    ]
    for key, value in config.normalized().to_dict().items():
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, int):
            rendered = str(value)
        elif isinstance(value, str):
            rendered = _toml_string(value)
        else:  # pragma: no cover - 配置字段类型固定
            raise TypeError(f"不支持的 TOML 值类型：{type(value)!r}")
        lines.append(f"{key} = {rendered}")
    return "\n".join(lines)


class ConfigStore:
    """负责 config.toml 的加载、迁移、损坏备份与原子写入。"""

    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path) if path is not None else config_path()
        self.legacy_path = (
            self.path.with_suffix(".json")
            if self.path.suffix.lower() == ".toml"
            else None
        )

    def load(self) -> Config:
        if self.path.exists():
            return self._load_toml()
        if self.legacy_path is not None and self.legacy_path.exists():
            return self._migrate_legacy_json()
        config = Config().normalized()
        self._try_save(config)
        return config

    def save(self, config: Config) -> None:
        config = config.normalized()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_name(self.path.name + ".tmp")
        payload = dump_toml(config) + "\n"
        try:
            with open(temp_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
        except BaseException:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def _load_toml(self) -> Config:
        try:
            raw = self.path.read_text(encoding="utf-8-sig")
            data = tomllib.loads(raw)
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
            logger.warning("读取 TOML 配置失败，将使用默认配置：%s", exc)
            self._backup_broken(self.path)
            config = Config().normalized()
            self._try_save(config)
            return config
        return Config.from_dict(data).normalized()

    def _migrate_legacy_json(self) -> Config:
        legacy = self.legacy_path
        assert legacy is not None
        config = Config().normalized()
        try:
            data = json.loads(legacy.read_text(encoding="utf-8-sig"))
            config = Config.from_dict(data).normalized()
            logger.info("从旧版 config.json 迁移配置：%s", legacy)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.warning("旧版 JSON 配置无法读取，将使用默认配置：%s", exc)

        if self._try_save(config):
            self._archive_legacy(legacy)
        return config

    def _try_save(self, config: Config) -> bool:
        try:
            self.save(config)
            return True
        except OSError:
            logger.exception("写入配置失败：%s", self.path)
            return False

    def _backup_broken(self, source: Path) -> None:
        if not source.exists():
            return
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = source.with_name(f"{source.name}.broken-{stamp}")
        try:
            os.replace(source, backup)
            logger.warning("已把损坏的配置备份为：%s", backup)
        except OSError:
            logger.exception("备份损坏配置失败：%s", source)

    def _archive_legacy(self, legacy: Path) -> None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = legacy.with_name(f"{legacy.name}.migrated-{stamp}")
        try:
            os.replace(legacy, backup)
            logger.info("旧版 JSON 配置已备份为：%s", backup)
        except OSError:
            logger.exception("备份旧版 JSON 配置失败：%s", legacy)
