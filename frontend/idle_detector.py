"""Idle detection — listens for global keyboard/mouse events via pynput."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

logger = logging.getLogger("assistant.idle_detector")

_last_activity = time.time()
_lock = threading.Lock()
_listeners: list[Any] = []


# ── Lazy import ──────────────────────────────────────────────
try:
    from pynput import keyboard, mouse

    _HAS_PYNPUT = True
except ImportError:
    _HAS_PYNPUT = False
    keyboard = None  # type: ignore
    mouse = None  # type: ignore


# ── Shared callback (debounced) ──────────────────────────────
_last_update_tick = 0.0


def _on_any_activity(*_args: Any) -> None:
    """Called on every input event; updates the activity timestamp (debounced)."""
    global _last_activity, _last_update_tick
    with _lock:
        now = time.time()
        if now - _last_update_tick >= 0.5:  # max 2 updates / sec
            _last_update_tick = now
            _last_activity = now


# ── Public API ───────────────────────────────────────────────

def get_idle_seconds() -> float:
    """Return seconds since the last detected keyboard/mouse event."""
    with _lock:
        return time.time() - _last_activity


def start_listeners() -> bool:
    """Start pynput listeners in daemon background threads.

    Returns True if listeners started, False if pynput is unavailable.
    """
    global _listeners
    if not _HAS_PYNPUT:
        logger.warning("pynput not installed — idle detection disabled")
        return False

    if _listeners:
        return True  # already running

    kl = keyboard.Listener(on_press=_on_any_activity, on_release=_on_any_activity)
    kl.daemon = True
    kl.start()
    _listeners.append(kl)

    ml = mouse.Listener(
        on_move=_on_any_activity,
        on_click=_on_any_activity,
        on_scroll=_on_any_activity,
    )
    ml.daemon = True
    ml.start()
    _listeners.append(ml)

    logger.info("Idle detection started (pynput)")
    return True


def stop_listeners() -> None:
    """Stop all pynput listeners."""
    global _listeners
    for lis in _listeners:
        try:
            lis.stop()
        except Exception:
            pass
    _listeners = []
    logger.info("Idle detection stopped")


# ── Auto-start on import ────────────────────────────────────
_listeners_started = start_listeners()
