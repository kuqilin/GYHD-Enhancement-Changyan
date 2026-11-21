# -*- coding: utf-8 -*-

from __future__ import annotations

import unittest

from main import build_parser


class CliTest(unittest.TestCase):
    def test_startup_flag(self) -> None:
        args = build_parser().parse_args(["--startup"])
        self.assertTrue(args.startup)
        self.assertFalse(args.wallpaper_only)

    def test_autostart_alias(self) -> None:
        args = build_parser().parse_args(["--autostart"])
        self.assertTrue(args.startup)

    def test_wallpaper_only(self) -> None:
        args = build_parser().parse_args(["--wallpaper-only"])
        self.assertTrue(args.wallpaper_only)
        self.assertFalse(args.startup)

    def test_skip_deploy(self) -> None:
        args = build_parser().parse_args(["--skip-deploy"])
        self.assertTrue(args.skip_deploy)


if __name__ == "__main__":
    unittest.main()
