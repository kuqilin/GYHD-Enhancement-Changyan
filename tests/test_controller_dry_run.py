# -*- coding: utf-8 -*-
"""回归测试：命令行 --dry-run 不能被 shutdown() 写进 config.toml。"""

from __future__ import annotations

import os
import shutil
import time
import unittest
from pathlib import Path

from gyhd.config import Config, ConfigStore

try:
    from PyQt5.QtCore import QCoreApplication

    from gyhd.controller import AppController
except ImportError:  # pragma: no cover - 没有 PyQt5 时跳过
    QCoreApplication = None
    AppController = None


@unittest.skipIf(AppController is None, "PyQt5 未安装")
class DryRunPersistenceTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp_root = Path(__file__).resolve().parent / "_tmp"
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.dir = tmp_root / f"dryrun-{os.getpid()}-{time.time_ns()}"
        self.dir.mkdir()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.path = self.dir / "config.toml"
        self.store = ConfigStore(self.path)
        self.store.save(Config(guard_dry_run=False))
        self.app = QCoreApplication.instance() or QCoreApplication([])

    def test_cli_override_does_not_persist(self) -> None:
        controller = AppController(self.store, dry_run_override=True)
        self.assertTrue(controller.dry_run_active)
        controller.shutdown()
        self.assertFalse(self.store.load().guard_dry_run)

    def test_config_dry_run_still_works(self) -> None:
        self.store.save(Config(guard_dry_run=True))
        controller = AppController(self.store)
        self.assertTrue(controller.dry_run_active)
        controller.shutdown()
        self.assertTrue(self.store.load().guard_dry_run)


if __name__ == "__main__":
    unittest.main()
