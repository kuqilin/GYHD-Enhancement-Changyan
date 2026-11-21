# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import shutil
import time
import unittest
from pathlib import Path

from gyhd.config import (
    MAX_GUARD_INTERVAL_MS,
    MIN_GUARD_INTERVAL_MS,
    Config,
    ConfigStore,
)
from gyhd.constants import DEFAULT_WALLPAPER_FOLDER


class ConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        # 必须把临时目录放在工作区内，且不能用 tempfile.mkdtemp：
        # 它创建的目录在 Windows 上带有过窄的 DACL，沙箱里的后续写入会被拒绝。
        tmp_root = Path(__file__).resolve().parent / "_tmp"
        tmp_root.mkdir(parents=True, exist_ok=True)
        self._tmp = tmp_root / f"config-{os.getpid()}-{time.time_ns()}"
        self._tmp.mkdir()
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.path = self._tmp / "config.json"
        self.store = ConfigStore(self.path)

    def test_missing_file_creates_default(self) -> None:
        config = self.store.load()
        self.assertTrue(self.path.is_file())
        self.assertEqual(config.wallpaper_folder, DEFAULT_WALLPAPER_FOLDER)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 1)

    def test_roundtrip(self) -> None:
        config = self.store.load()
        config.wallpaper_folder = r"D:\Pictures\Wallpapers"
        config.guard_enabled = False
        config.guard_interval_ms = 750
        config.kill_only_during_slideshow = False
        config.guard_dry_run = True
        self.store.save(config)

        loaded = self.store.load()
        self.assertEqual(loaded.wallpaper_folder, r"D:\Pictures\Wallpapers")
        self.assertFalse(loaded.guard_enabled)
        self.assertEqual(loaded.guard_interval_ms, 750)
        self.assertFalse(loaded.kill_only_during_slideshow)
        self.assertTrue(loaded.guard_dry_run)
        self.assertFalse((Path(str(self.path) + ".tmp")).exists())

    def test_corrupt_file_is_backed_up(self) -> None:
        self.path.write_text("{ not json", encoding="utf-8")
        config = self.store.load()
        self.assertEqual(config.wallpaper_folder, DEFAULT_WALLPAPER_FOLDER)
        backups = list(self.path.parent.glob("config.json.broken-*"))
        self.assertEqual(len(backups), 1)
        self.assertTrue(json.loads(self.path.read_text(encoding="utf-8")))

    def test_non_dict_root_is_treated_as_default(self) -> None:
        self.path.write_text("[]", encoding="utf-8")
        config = self.store.load()
        self.assertEqual(config.wallpaper_folder, DEFAULT_WALLPAPER_FOLDER)

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
            json.dumps(
                {
                    "wallpaper_folder": r"E:\Pics",
                    "future_option": {"nested": True},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        config = self.store.load()
        self.assertEqual(config.wallpaper_folder, r"E:\Pics")
        self.assertTrue(config.guard_enabled)

    def test_empty_folder_falls_back_to_default(self) -> None:
        self.path.write_text(
            json.dumps({"wallpaper_folder": "   "}), encoding="utf-8"
        )
        config = self.store.load()
        self.assertEqual(config.wallpaper_folder, DEFAULT_WALLPAPER_FOLDER)


if __name__ == "__main__":
    unittest.main()
