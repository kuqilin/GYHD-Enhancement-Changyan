# -*- coding: utf-8 -*-

from __future__ import annotations

import unittest

from gyhd.winwindow import WindowInfo


def window(
    rect: tuple[int, int, int, int],
    monitor_rect: tuple[int, int, int, int] | None,
) -> WindowInfo:
    return WindowInfo(
        hwnd=1,
        pid=1,
        process_name="wpp.exe",
        class_name="Qt5QWindowIcon",
        title="demo",
        visible=True,
        rect=rect,
        monitor_rect=monitor_rect,
    )


class FullscreenTest(unittest.TestCase):
    def test_exact_match(self) -> None:
        self.assertTrue(window((0, 0, 1920, 1080), (0, 0, 1920, 1080)).is_fullscreen())

    def test_tolerance(self) -> None:
        self.assertTrue(
            window((-1, -1, 1921, 1081), (0, 0, 1920, 1080)).is_fullscreen()
        )

    def test_not_fullscreen(self) -> None:
        self.assertFalse(
            window((0, 0, 1920, 1000), (0, 0, 1920, 1080)).is_fullscreen()
        )

    def test_unknown_monitor(self) -> None:
        self.assertFalse(window((0, 0, 1920, 1080), None).is_fullscreen())


if __name__ == "__main__":
    unittest.main()
