# -*- coding: utf-8 -*-
"""单实例互斥锁，避免后台守护被启动多份。"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os

from .constants import APP_ID

ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    def __init__(self, name: str = APP_ID) -> None:
        self._handle = None
        self.already_running = False
        if os.name != "nt":
            return

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [wt.LPVOID, wt.BOOL, wt.LPCWSTR]
        kernel32.CreateMutexW.restype = wt.HANDLE
        kernel32.CloseHandle.argtypes = [wt.HANDLE]
        kernel32.CloseHandle.restype = wt.BOOL

        ctypes.set_last_error(0)
        handle = kernel32.CreateMutexW(None, False, f"Local\\{name}")
        if handle:
            self._handle = handle
            self.already_running = (
                ctypes.get_last_error() == ERROR_ALREADY_EXISTS
            )
        self._kernel32 = kernel32

    def close(self) -> None:
        if self._handle and getattr(self, "_kernel32", None):
            self._kernel32.CloseHandle(self._handle)
            self._handle = None
