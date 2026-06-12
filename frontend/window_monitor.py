"""Window monitor — tracks active window changes via polling."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

logger = logging.getLogger("assistant.window_monitor")

# ── Lazy imports (fail gracefully if missing) ──────────────────
_HAS_WIN32 = False
_HAS_PSUTIL = False

try:
    import win32gui
    import win32process
    _HAS_WIN32 = True
except ImportError:
    logger.warning("pywin32 not installed. Run: pip install pywin32")

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    logger.warning("psutil not installed. Run: pip install psutil")


class WindowMonitor:
    """Poll the foreground window and fire a callback when it changes.

    Usage
    -----
        def on_window_change(title, proc_name):
            print(f"Switched to [{proc_name}] {title}")

        monitor = WindowMonitor()
        monitor.start_polling(2000, on_window_change)
        ...
        monitor.stop_polling()
    """

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._running = False
        self._last_key: tuple[str | None, str | None] = (None, None)

    # ── Public API ───────────────────────────────────────────

    def get_active_window(self) -> tuple[str | None, str | None]:
        """Return ``(window_title, process_name)`` for the current foreground window.

        Returns ``(None, None)`` on any error (invalid handle, dead process …).
        """
        if not _HAS_WIN32 or not _HAS_PSUTIL:
            return None, None

        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return None, None

            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc_name = psutil.Process(pid).name()
            return title or None, proc_name

        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            return None, None

    def start_polling(
        self,
        interval_ms: int = 2000,
        callback: Callable[[str | None, str | None], None] | None = None,
    ) -> None:
        """Begin polling the foreground window in a daemon background thread.

        Parameters
        ----------
        interval_ms : int
            Polling interval in milliseconds (default 2000).
        callback : callable or None
            Called with ``(title, process_name)`` whenever the active window changes.
        """
        if self._running:
            logger.warning("WindowMonitor already polling")
            return

        self._running = True
        self._last_key = (None, None)
        self._thread = threading.Thread(
            target=_poll_loop,
            args=(self, interval_ms / 1000, callback),
            daemon=True,
            name="window-monitor",
        )
        self._thread.start()
        logger.info("WindowMonitor started (interval=%.1fs)", interval_ms / 1000)

    def stop_polling(self) -> None:
        """Stop the polling thread."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        logger.info("WindowMonitor stopped")


# ── Background thread target ──────────────────────────────────

def _poll_loop(
    monitor: WindowMonitor,
    interval: float,
    callback: Callable[[str | None, str | None], None] | None,
) -> None:
    """Daemon thread: poll *interval* seconds and call *callback* on change."""
    while monitor._running:
        try:
            current = monitor.get_active_window()
            # Only fire callback when the window *title* actually changed
            if current != monitor._last_key:
                monitor._last_key = current
                if callback is not None:
                    callback(current[0], current[1])
        except Exception:
            logger.exception("WindowMonitor poll error")

        time.sleep(interval)


# ═══════════════════════════════════════════════════════════════
# Example usage
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    def on_window_change(title: str | None, proc: str | None) -> None:
        if title is None:
            return

        lower = title.lower()

        if "chrome" in lower or "edge" in lower or "firefox" in lower:
            tag = "[Web] 浏览网页"
        elif "code" in lower and ("visual" in lower or "vs" in lower):
            tag = "[Code] 写代码"
        elif "spotify" in lower or "music" in lower:
            tag = "[Music] 听音乐"
        elif "word" in lower or "excel" in lower or "powerpoint" in lower or "onenote" in lower:
            tag = "[Office] 办公文档"
        elif "slack" in lower or "teams" in lower or "discord" in lower or "wechat" in lower or "qq" in lower:
            tag = "[Chat] 聊天沟通"
        elif "terminal" in lower or "powershell" in lower or "cmd" in lower:
            tag = "[Terminal] 终端"
        else:
            tag = "[?] 其他活动"

        print(f"[{proc}] {tag}: {title}")

    monitor = WindowMonitor()
    monitor.start_polling(2000, on_window_change)

    try:
        print("Polling active windows (Ctrl+C to stop)...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\\nStopping...")
    finally:
        monitor.stop_polling()
