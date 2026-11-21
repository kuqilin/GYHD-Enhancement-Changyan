# -*- coding: utf-8 -*-

from __future__ import annotations

import unittest

from gyhd.winproc import ProcessInfo
from gyhd.winwindow import WindowInfo
from gyhd.wps_guard import (
    WpsGuard,
    is_recorder_process,
    is_slideshow_window,
)

FULLSCREEN = (0, 0, 1920, 1080)


def window(
    *,
    process: str = "wpp.exe",
    class_name: str = "Qt5QWindowIcon",
    title: str = "WPS Presentation Slide Show - [demo.pptx]",
    visible: bool = True,
    rect: tuple[int, int, int, int] = FULLSCREEN,
    monitor_rect: tuple[int, int, int, int] | None = FULLSCREEN,
) -> WindowInfo:
    return WindowInfo(
        hwnd=1,
        pid=100,
        process_name=process,
        class_name=class_name,
        title=title,
        visible=visible,
        rect=rect,
        monitor_rect=monitor_rect,
    )


def process(
    name: str,
    exe: str,
    pid: int = 200,
) -> ProcessInfo:
    return ProcessInfo(pid=pid, name=name, exe=exe)


APOWER = process(
    "ApowerREC.exe",
    r"C:\Users\A\AppData\Roaming\Kingsoft\wps\addons\pool\win-i386"
    r"\kapower_2.2.0.7\kapowerapp\ApowerREC.exe",
    300,
)
WPS = process(
    "wps.exe",
    r"D:\Softwares\WPS Office\12.1.0.22089\office6\wps.exe",
    400,
)
NOTEPAD = process("notepad.exe", r"C:\Windows\System32\notepad.exe", 500)


class SlideshowDetectionTest(unittest.TestCase):
    def test_english_title(self) -> None:
        self.assertTrue(is_slideshow_window(window()))

    def test_chinese_title(self) -> None:
        self.assertTrue(is_slideshow_window(window(title="WPS 演示 - 幻灯片放映")))

    def test_fullscreen_qt_window_with_custom_title(self) -> None:
        self.assertTrue(is_slideshow_window(window(title="demo.pptx")))

    def test_editor_window_is_not_slideshow(self) -> None:
        self.assertFalse(
            is_slideshow_window(
                window(
                    process="wps.exe",
                    class_name="PP12FrameClass",
                    title="demo.pptx - WPS Office",
                )
            )
        )

    def test_fullscreen_editor_with_show_in_filename(self) -> None:
        self.assertFalse(
            is_slideshow_window(
                window(
                    process="wps.exe",
                    class_name="PP12FrameClass",
                    title="放映计划.pptx - WPS Office",
                )
            )
        )

    def test_show_frame_class_with_weak_title(self) -> None:
        self.assertTrue(
            is_slideshow_window(
                window(
                    class_name="PP12ShowFrame",
                    title="WPS 演示 - 放映",
                )
            )
        )

    def test_invisible_window_is_not_slideshow(self) -> None:
        self.assertFalse(is_slideshow_window(window(visible=False)))

    def test_non_wps_process_is_not_slideshow(self) -> None:
        self.assertFalse(is_slideshow_window(window(process="notepad.exe")))

    def test_small_window_is_not_slideshow(self) -> None:
        # 标题不含放映关键字时，只有“Qt 全屏窗口”才按放映处理。
        self.assertFalse(
            is_slideshow_window(
                window(title="demo.pptx", rect=(0, 0, 800, 600))
            )
        )


class RecorderDetectionTest(unittest.TestCase):
    def test_apowerrec_plugin(self) -> None:
        self.assertTrue(is_recorder_process(APOWER))

    def test_helper_in_kapower_folder(self) -> None:
        helper = process(
            "ffmpeg.exe",
            r"C:\Users\A\AppData\Roaming\Kingsoft\wps\addons\pool\win-i386"
            r"\kapower_2.2.0.7\kapowerapp\ffmpeg.exe",
        )
        self.assertTrue(is_recorder_process(helper))

    def test_standalone_apowerrec(self) -> None:
        self.assertTrue(
            is_recorder_process(
                process("ApowerREC.exe", r"C:\Program Files\ApowerREC\ApowerREC.exe")
            )
        )

    def test_wps_is_not_recorder(self) -> None:
        self.assertFalse(is_recorder_process(WPS))

    def test_notepad_is_not_recorder(self) -> None:
        self.assertFalse(is_recorder_process(NOTEPAD))

    def test_wpsrecorder_name(self) -> None:
        self.assertTrue(
            is_recorder_process(
                process("wpsrecorder.exe", r"C:\Somewhere\wpsrecorder.exe")
            )
        )


class GuardDecisionTest(unittest.TestCase):
    def _guard(
        self,
        *,
        windows: list[WindowInfo],
        processes: list[ProcessInfo],
        kill_only_during_slideshow: bool = True,
        dry_run: bool = False,
        killer=None,
        self_pid: int = 999,
        now: float = 42.0,
    ) -> tuple[WpsGuard, list[int]]:
        killed_pids: list[int] = []

        def default_killer(pid: int) -> bool:
            killed_pids.append(pid)
            return True

        guard = WpsGuard(
            kill_only_during_slideshow=kill_only_during_slideshow,
            dry_run=dry_run,
            window_lister=lambda: windows,
            process_lister=lambda: processes,
            killer=killer or default_killer,
            clock=lambda: now,
            self_pid=self_pid,
        )
        return guard, killed_pids

    def test_kills_recorder_during_slideshow(self) -> None:
        guard, killed = self._guard(
            windows=[window()], processes=[WPS, APOWER, NOTEPAD]
        )
        snapshot = guard.poll()
        self.assertTrue(snapshot.slideshow_active)
        self.assertTrue(snapshot.wps_running)
        self.assertEqual(killed, [300])
        self.assertEqual(len(snapshot.killed), 1)
        self.assertEqual(snapshot.killed[0].name, "ApowerREC.exe")
        self.assertEqual(snapshot.killed[0].timestamp, 42.0)
        self.assertEqual(snapshot.failures, ())

    def test_does_not_kill_outside_slideshow(self) -> None:
        editor = window(
            process="wps.exe",
            class_name="PP12FrameClass",
            title="demo.pptx - WPS Office",
        )
        guard, killed = self._guard(
            windows=[editor], processes=[WPS, APOWER]
        )
        snapshot = guard.poll()
        self.assertFalse(snapshot.slideshow_active)
        self.assertTrue(snapshot.wps_running)
        self.assertEqual(killed, [])
        self.assertEqual(len(snapshot.recorders), 1)

    def test_kill_everywhere_when_configured(self) -> None:
        guard, killed = self._guard(
            windows=[],
            processes=[APOWER],
            kill_only_during_slideshow=False,
        )
        snapshot = guard.poll()
        self.assertEqual(killed, [300])
        self.assertFalse(snapshot.wps_running)

    def test_dry_run_does_not_kill(self) -> None:
        guard, killed = self._guard(
            windows=[window()], processes=[APOWER], dry_run=True
        )
        snapshot = guard.poll()
        self.assertEqual(killed, [])
        self.assertEqual(snapshot.killed, ())
        self.assertEqual(len(snapshot.would_kill), 1)
        self.assertEqual(snapshot.would_kill[0].pid, 300)

    def test_kill_failure_is_recorded(self) -> None:
        guard, _ = self._guard(
            windows=[window()],
            processes=[APOWER],
            killer=lambda pid: False,
        )
        snapshot = guard.poll()
        self.assertEqual(snapshot.killed, ())
        self.assertEqual(len(snapshot.failures), 1)
        self.assertEqual(snapshot.failures[0].pid, 300)

    def test_never_kills_self(self) -> None:
        guard, killed = self._guard(
            windows=[window()], processes=[APOWER], self_pid=300
        )
        snapshot = guard.poll()
        self.assertEqual(killed, [])
        self.assertEqual(snapshot.recorders, ())


if __name__ == "__main__":
    unittest.main()
