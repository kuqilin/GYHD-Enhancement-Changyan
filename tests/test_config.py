# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import shutil
import time
import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib

from gyhd.config import (
    MAX_GUARD_INTERVAL_MS,
    MIN_GUARD_INTERVAL_MS,
    Config,
    ConfigStore,
    dump_toml,
)
from gyhd.constants import DEFAULT_WALLPAPER_FOLDER


class ConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp_root = Path(__file__).resolve().parent / "_tmp"
        tmp_root.mkdir(parents=True, exist_ok=True)
        self._tmp = tmp_root / f"config-{os.getpid()}-{time.time_ns()}"
        self._tmp.mkdir()
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.path = self._tmp / "config.toml"
        self.legacy_path = self._tmp / "config.json"
        self.store = ConfigStore(self.path)

    def test_missing_file_creates_toml(self) -> None:
        config = self.store.load()
        self.assertTrue(self.path.is_file())
        self.assertEqual(config.wallpaper_folder, DEFAULT_WALLPAPER_FOLDER)
        data = tomllib.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 1)
        self.assertFalse(data["guard_dry_run"])

    def test_roundtrip(self) -> None:
        config = self.store.load()
        config.wallpaper_folder = r"D:\Pictures\Wallpapers"
        config.guard_enabled = False
        config.guard_interval_ms = 750
        config.kill_only_during_slideshow = False
        config.guard_dry_run = True
        config.autostart = False
        self.store.save(config)

        loaded = self.store.load()
        self.assertEqual(loaded.wallpaper_folder, r"D:\Pictures\Wallpapers")
        self.assertFalse(loaded.guard_enabled)
        self.assertEqual(loaded.guard_interval_ms, 750)
        self.assertFalse(loaded.kill_only_during_slideshow)
        self.assertTrue(loaded.guard_dry_run)
        self.assertFalse(loaded.autostart)
        self.assertFalse((self._tmp / "config.toml.tmp").exists())

    def test_corrupt_toml_is_backed_up(self) -> None:
        self.path.write_text('wallpaper_folder = "unterminated\n', encoding="utf-8")
        config = self.store.load()
        self.assertEqual(config.wallpaper_folder, DEFAULT_WALLPAPER_FOLDER)
        backups = list(self._tmp.glob("config.toml.broken-*"))
        self.assertEqual(len(backups), 1)
        self.assertTrue(tomllib.loads(self.path.read_text(encoding="utf-8")))

    def test_wrong_value_type_falls_back(self) -> None:
        self.path.write_text(
            'wallpaper_folder = 123\nguard_interval_ms = "bad"\n',
            encoding="utf-8",
        )
        config = self.store.load()
        self.assertEqual(config.wallpaper_folder, DEFAULT_WALLPAPER_FOLDER)
        self.assertEqual(config.guard_interval_ms, 500)

    def test_interval_is_clamped(self) -> None:
        self.assertEqual(
            Config(guard_interval_ms=10).normalized().guard_interval_ms,
            MIN_GUARD_INTERVAL_MS,
        )
        self.assertEqual(
            Config(guard_interval_ms=999999).normalized().guard_interval_ms,
            MAX_GUARD_INTERVAL_MS,
        )
        self.assertEqual(
            Config(guard_interval_ms="bad").normalized().guard_interval_ms, 500
        )

    def test_unknown_fields_are_ignored(self) -> None:
        self.path.write_text(
            "\n".join(
                [
                    'wallpaper_folder = "E:\\\\Pics"',
                    "[future]",
                    "nested = true",
                ]
            ),
            encoding="utf-8",
        )
        config = self.store.load()
        self.assertEqual(config.wallpaper_folder, r"E:\Pics")
        self.assertTrue(config.guard_enabled)

    def test_empty_folder_falls_back_to_default(self) -> None:
        self.path.write_text('wallpaper_folder = "   "\n', encoding="utf-8")
        config = self.store.load()
        self.assertEqual(config.wallpaper_folder, DEFAULT_WALLPAPER_FOLDER)

    def test_literal_toml_path(self) -> None:
        self.path.write_text(
            "wallpaper_folder = 'D:\\花都校区定制壁纸'\n", encoding="utf-8"
        )
        config = self.store.load()
        self.assertEqual(config.wallpaper_folder, r"D:\花都校区定制壁纸")

    def test_dump_toml_escapes_windows_path(self) -> None:
        text = dump_toml(Config(wallpaper_folder=r"D:\花都校区定制壁纸"))
        self.assertIn(r'"D:\\花都校区定制壁纸"', text)
        parsed = tomllib.loads(text)
        self.assertEqual(parsed["wallpaper_folder"], r"D:\花都校区定制壁纸")

    def test_migrates_legacy_json(self) -> None:
        self.legacy_path.write_text(
            json.dumps(
                {
                    "wallpaper_folder": r"E:\OldPics",
                    "guard_enabled": False,
                    "guard_dry_run": True,
                    "future_key": 1,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        config = self.store.load()
        self.assertEqual(config.wallpaper_folder, r"E:\OldPics")
        self.assertFalse(config.guard_enabled)
        self.assertTrue(config.guard_dry_run)
        self.assertTrue(self.path.is_file())
        self.assertFalse(self.legacy_path.exists())
        self.assertEqual(len(list(self._tmp.glob("config.json.migrated-*"))), 1)

    def test_corrupt_legacy_json_is_archived(self) -> None:
        self.legacy_path.write_text("{ not json", encoding="utf-8")
        config = self.store.load()
        self.assertEqual(config.wallpaper_folder, DEFAULT_WALLPAPER_FOLDER)
        self.assertTrue(self.path.is_file())
        self.assertFalse(self.legacy_path.exists())
        self.assertEqual(len(list(self._tmp.glob("config.json.migrated-*"))), 1)

    def test_toml_wins_over_legacy_json(self) -> None:
        self.store.save(Config(wallpaper_folder=r"F:\TomlPics"))
        self.legacy_path.write_text(
            json.dumps({"wallpaper_folder": r"G:\JsonPics"}),
            encoding="utf-8",
        )
        config = self.store.load()
        self.assertEqual(config.wallpaper_folder, r"F:\TomlPics")
        self.assertTrue(self.legacy_path.exists())


if __name__ == "__main__":
    unittest.main()
