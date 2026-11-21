# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
import os
import shutil
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtGui import QColor, QGuiApplication, QImage  # noqa: E402

from gyhd.overlay import cleanup_generated, render_wallpaper  # noqa: E402
from gyhd.weather import Temperature  # noqa: E402


class OverlayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QGuiApplication.instance()
        if cls.app is None:
            cls.app = QGuiApplication([])

    def setUp(self) -> None:
        tmp_root = Path(__file__).resolve().parent / "_tmp"
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.root = tmp_root / f"overlay-{os.getpid()}-{time.time_ns()}"
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

        self.source = self.root / "source.png"
        image = QImage(400, 300, QImage.Format_RGB32)
        image.fill(QColor("#336699"))
        self.assertTrue(image.save(str(self.source), "PNG"))

    def test_render_does_not_modify_source(self) -> None:
        before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        output = render_wallpaper(
            self.source,
            stage="高三",
            exam="高考",
            days=197,
            temperature=Temperature(15, 25),
            destination_dir=self.root / "out",
        )
        after = hashlib.sha256(self.source.read_bytes()).hexdigest()

        self.assertEqual(before, after)
        self.assertTrue(output.is_file())
        self.assertEqual(output.suffix, ".jpg")
        rendered = QImage(str(output))
        self.assertEqual((rendered.width(), rendered.height()), (400, 300))

    def test_render_without_weather(self) -> None:
        output = render_wallpaper(
            self.source,
            stage="初三",
            exam="中考",
            days=0,
            temperature=None,
            destination_dir=self.root / "out",
        )
        self.assertTrue(output.is_file())

    def test_cleanup_keeps_newest(self) -> None:
        folder = self.root / "cleanup"
        folder.mkdir()
        for index in range(7):
            path = folder / f"wallpaper-{index}.jpg"
            path.write_bytes(b"x")
            os.utime(path, (1000 + index, 1000 + index))

        cleanup_generated(keep=3, folder=folder)
        remaining = sorted(folder.glob("wallpaper-*.jpg"))
        self.assertEqual(len(remaining), 3)
        self.assertEqual(
            [path.name for path in remaining],
            ["wallpaper-4.jpg", "wallpaper-5.jpg", "wallpaper-6.jpg"],
        )


if __name__ == "__main__":
    unittest.main()
