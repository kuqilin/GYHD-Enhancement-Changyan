# -*- coding: utf-8 -*-
"""进程枚举与结束（ctypes / Win32）。"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    wt.HANDLE,
    wt.DWORD,
    wt.LPWSTR,
    ctypes.POINTER(wt.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wt.BOOL
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.CloseHandle.restype = wt.BOOL
kernel32.TerminateProcess.argtypes = [wt.HANDLE, wt.UINT]
kernel32.TerminateProcess.restype = wt.BOOL

psapi.EnumProcesses.argtypes = [
    ctypes.POINTER(wt.DWORD),
    wt.DWORD,
    ctypes.POINTER(wt.DWORD),
]
psapi.EnumProcesses.restype = wt.BOOL


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    name: str
    exe: str


def process_path(pid: int) -> str:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        size = wt.DWORD(len(buffer))
        if kernel32.QueryFullProcessImageNameW(
            handle, 0, buffer, ctypes.byref(size)
        ):
            return buffer.value
        return ""
    finally:
        kernel32.CloseHandle(handle)


def list_processes() -> list[ProcessInfo]:
    capacity = 4096
    while True:
        array = (wt.DWORD * capacity)()
        needed = wt.DWORD()
        if not psapi.EnumProcesses(
            array, ctypes.sizeof(array), ctypes.byref(needed)
        ):
            logger.debug("EnumProcesses 失败，Win32 错误=%s", ctypes.get_last_error())
            return []
        count = needed.value // ctypes.sizeof(wt.DWORD)
        if count < capacity:
            break
        capacity *= 2

    result: list[ProcessInfo] = []
    seen: set[int] = set()
    for pid in array[:count]:
        pid = int(pid)
        if pid <= 0 or pid in seen:
            continue
        seen.add(pid)
        exe = process_path(pid)
        if not exe:
            continue
        result.append(ProcessInfo(pid=pid, name=os.path.basename(exe), exe=exe))
    return result


def terminate_process(pid: int, exit_code: int = 1) -> bool:
    if pid <= 0 or pid == os.getpid():
        return False
    handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if not handle:
        logger.debug(
            "打开进程失败 pid=%s，Win32 错误=%s", pid, ctypes.get_last_error()
        )
        return False
    try:
        return bool(kernel32.TerminateProcess(handle, exit_code))
    finally:
        kernel32.CloseHandle(handle)


def is_process_running(name: str) -> bool:
    target = name.casefold()
    return any(item.name.casefold() == target for item in list_processes())
