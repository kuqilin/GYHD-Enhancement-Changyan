# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import shutil
import time
import unittest
from pathlib import Path
from unittest import mock

from gyhd import deployment


class DeploymentTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp_root = Path(__file__).resolve().parent / "_tmp"
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.root = tmp_root / f"deploy-{os.getpid()}-{time.time_ns()}"
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _make_source(self) -> Path:
        source = self.root / "source"
        (source / "gyhd").mkdir(parents=True)
        (source / "assets").mkdir()
        (source / "tests").mkdir()
        (source / "runtime").mkdir()
        (source / ".git").mkdir()
        (source / "main.py").write_text("print('hi')\n", encoding="utf-8")
        (source / "gyhd" / "__init__.py").write_text("", encoding="utf-8")
        (source / "assets" / "GY_1080x1080.ico").write_bytes(b"ico")
        (source / "tests" / "test_x.py").write_text("", encoding="utf-8")
        (source / "runtime" / "log.txt").write_text("", encoding="utf-8")
        (source / ".git" / "config").write_text("", encoding="utf-8")
        (source / "config.toml").write_text("", encoding="utf-8")
        return source

    def test_copy_app_tree_ignores_runtime_and_tests(self) -> None:
        source = self._make_source()
        target = self.root / "target"
        deployment.copy_app_tree(source, target)

        self.assertTrue((target / "main.py").is_file())
        self.assertTrue((target / "gyhd" / "__init__.py").is_file())
        self.assertTrue((target / "assets" / "GY_1080x1080.ico").is_file())
        self.assertFalse((target / "tests").exists())
        self.assertFalse((target / "runtime").exists())
        self.assertFalse((target / ".git").exists())
        self.assertFalse((target / "config.toml").exists())

    def test_is_installed_source_layout(self) -> None:
        target = self.root / "installed"
        (target / "gyhd").mkdir(parents=True)
        (target / "main.py").write_text("", encoding="utf-8")
        self.assertFalse(deployment.is_installed(target, frozen=False))
        (target / "gyhd" / "__init__.py").write_text("", encoding="utf-8")
        self.assertTrue(deployment.is_installed(target, frozen=False))

    def test_install_dir_env_override(self) -> None:
        override = self.root / "custom-install"
        with mock.patch.dict(
            os.environ, {deployment.INSTALL_DIR_ENV: str(override)}, clear=False
        ):
            self.assertEqual(deployment.install_dir(), override)

    def test_shortcut_spec_uses_startup_argument(self) -> None:
        source = self._make_source()
        spec = deployment.shortcut_spec(source)
        self.assertEqual(spec.working_dir, source)
        self.assertIn("--startup", spec.arguments)
        self.assertIn("main.py", spec.arguments)
        self.assertIsNotNone(spec.icon)
        self.assertTrue(spec.icon.is_file())

    def test_should_deploy_false_when_installed(self) -> None:
        target = self.root / "already"
        (target / "gyhd").mkdir(parents=True)
        (target / "main.py").write_text("", encoding="utf-8")
        (target / "gyhd" / "__init__.py").write_text("", encoding="utf-8")
        with mock.patch.dict(
            os.environ, {deployment.INSTALL_DIR_ENV: str(target)}, clear=False
        ), mock.patch.object(deployment, "current_root", return_value=self.root):
            self.assertFalse(deployment.should_deploy())

    def test_should_deploy_false_when_target_inside_source(self) -> None:
        target = self.root / "source" / "sub"
        with mock.patch.dict(
            os.environ, {deployment.INSTALL_DIR_ENV: str(target)}, clear=False
        ):
            source = self.root / "source"
            source.mkdir()
            with mock.patch.object(deployment, "current_root", return_value=source):
                self.assertFalse(deployment.should_deploy())


if __name__ == "__main__":
    unittest.main()
