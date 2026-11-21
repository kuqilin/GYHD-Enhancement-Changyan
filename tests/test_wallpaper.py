# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import random
import shutil
import time
import unittest
from pathlib import Path
from unittest import mock

from gyhd.wallpaper import (
    SPIF_SENDCHANGE,
    SPIF_UPDATEINIFILE,
    WallpaperError,
    change_to_random,
    list_images,
    pick_random_image,
    set_wallpaper,
)


class WallpaperTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp_root = Path(__file__).resolve().parent / "_tmp"
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.root = tmp_root / f"wallpaper-{os.getpid()}-{time.time_ns()}"
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / "b.JPG").write_bytes(b"jpg")
        (self.root / "a.png").write_bytes(b"png")
        (self.root / "note.txt").write_text("x", encoding="utf-8")
        (self.root / "dir.jpg").mkdir()

    def test_list_images_filters_and_sorts(self) -> None:
        names = [path.name for path in list_images(self.root)]
        self.assertEqual(names, ["a.png", "b.JPG"])

    def test_list_images_missing_folder(self) -> None:
        self.assertEqual(list_images(self.root / "missing"), [])

    def test_pick_random_image_empty(self) -> None:
        with self.assertRaises(WallpaperError):
            pick_random_image([])

    def test_pick_random_image_avoids_current(self) -> None:
        images = [self.root / "a.png", self.root / "b.JPG"]
        chosen = pick_random_image(
            images, current=str(images[0]), rng=random.Random(0)
        )
        self.assertEqual(chosen.name, "b.JPG")

    def test_set_wallpaper_missing_file(self) -> None:
        calls: list[tuple[str, int]] = []

        def fake_spi(path: str, flags: int) -> bool:
            calls.append((path, flags))
            return True

        with self.assertRaises(WallpaperError):
            set_wallpaper(
                self.root / "nope.jpg", spi=fake_spi, apply_style=False
            )
        self.assertEqual(calls, [])

    def test_set_wallpaper_success(self) -> None:
        calls: list[tuple[str, int]] = []

        def fake_spi(path: str, flags: int) -> bool:
            calls.append((path, flags))
            return True

        result = set_wallpaper(
            self.root / "a.png", spi=fake_spi, apply_style=False
        )
        self.assertEqual(result.name, "a.png")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], SPIF_UPDATEINIFILE | SPIF_SENDCHANGE)

    def test_set_wallpaper_failure(self) -> None:
        def fake_spi(path: str, flags: int) -> bool:
            return False

        with self.assertRaises(WallpaperError) as ctx:
            set_wallpaper(
                self.root / "a.png", spi=fake_spi, apply_style=False
            )
        self.assertIn("返回 0", str(ctx.exception))

    def test_change_to_random(self) -> None:
        calls: list[str] = []

        def fake_spi(path: str, flags: int) -> bool:
            calls.append(path)
            return True

        with mock.patch("gyhd.wallpaper.current_wallpaper", return_value=""):
            result = change_to_random(
                self.root, spi=fake_spi, rng=random.Random(1)
            )
        self.assertIn(result.name, {"a.png", "b.JPG"})
        self.assertEqual(len(calls), 1)

    def test_change_to_random_empty_folder(self) -> None:
        with self.assertRaises(WallpaperError):
            change_to_random(self.root / "missing", spi=lambda p, f: True)

    def test_change_to_random_transform(self) -> None:
        overlay = self.root / "overlay.jpg"
        overlay.write_bytes(b"overlay")
        calls: list[str] = []

        def fake_spi(path: str, flags: int) -> bool:
            calls.append(path)
            return True

        with mock.patch("gyhd.wallpaper.current_wallpaper", return_value=""):
            result = change_to_random(
                self.root,
                spi=fake_spi,
                rng=random.Random(2),
                transform=lambda source: overlay,
            )
        self.assertEqual(result, overlay)
        self.assertEqual(calls, [str(overlay)])


if __name__ == "__main__":
    unittest.main()
