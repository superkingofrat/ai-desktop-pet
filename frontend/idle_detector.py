"""Idle detection — Windows-only, uses GetLastInputInfo."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

_USER32 = ctypes.windll.user32
_KERNEL32 = ctypes.windll.kernel32


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def get_idle_seconds() -> int:
    """Return seconds since last keyboard/mouse input.

    Returns 0 if the API call fails or the result seems invalid (> 1 hour).
    """
    try:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(_LASTINPUTINFO)

        if not _USER32.GetLastInputInfo(ctypes.byref(info)):
            return 0

        current_ticks = _KERNEL32.GetTickCount()
        if current_ticks < info.dwTime:  # overflow
            return 0

        idle_ms = current_ticks - info.dwTime
        if idle_ms > 3_600_000:  # > 1 hour = likely bug
            return 0

        return max(0, idle_ms // 1000)

    except Exception:
        return 0
