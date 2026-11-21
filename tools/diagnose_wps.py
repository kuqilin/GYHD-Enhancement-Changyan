# -*- coding: utf-8 -*-
"""只读诊断：打印 WPS 窗口、放映判定和录屏进程匹配结果。

用法：
    python tools/diagnose_wps.py

不会结束任何进程。适合在 WPS 升级后确认匹配关键字是否仍然有效。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 允许直接 `python tools/diagnose_wps.py` 时从项目根导入 gyhd。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gyhd.constants import WPS_PROCESS_NAMES  # noqa: E402
from gyhd.winproc import list_processes  # noqa: E402
from gyhd.winwindow import list_top_level_windows  # noqa: E402
from gyhd.wps_guard import (  # noqa: E402
    is_recorder_process,
    is_slideshow_window,
    is_wps_process,
)


def main() -> int:
    print("== WPS 顶层窗口 ==")
    show_found = False
    wps_found = False
    for window in list_top_level_windows():
        if not is_wps_process(window.process_name):
            continue
        wps_found = True
        slideshow = is_slideshow_window(window)
        show_found = show_found or slideshow
        print(
            f"pid={window.pid:<6} process={window.process_name:<8} "
            f"class={window.class_name!r:<28} "
            f"fullscreen={window.is_fullscreen()} slideshow={slideshow} "
            f"title={window.title!r}"
        )
    if not wps_found:
        print("(没有发现 WPS 窗口；WPS 可能没在运行)")

    print("\n== 匹配到的录屏进程 ==")
    recorders = [p for p in list_processes() if is_recorder_process(p)]
    if not recorders:
        print("(没有发现 ApowerREC / kapower 录屏进程)")
    for process in recorders:
        print(f"pid={process.pid:<6} name={process.name:<20} exe={process.exe}")

    print("\n== 结论 ==")
    print(f"WPS 在运行 : {wps_found}")
    print(f"正在放映   : {show_found}")
    print(f"录屏进程   : {len(recorders)} 个")
    if wps_found and not show_found:
        print("提示：放映时仍显示 False，说明放映窗口的类名/标题可能变了，")
        print("      请把上面 WPS 窗口的 class/title 发出来，更新 gyhd/constants.py。")
    if WPS_PROCESS_NAMES:
        print(f"当前接受的 WPS 进程名：{sorted(WPS_PROCESS_NAMES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
