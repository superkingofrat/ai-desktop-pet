"""Unified launcher — starts backend (uvicorn) and frontend (PyQt5) together.

Usage:
    python run.py                  # default port 8000
    python run.py --port 8080      # custom port
"""

from __future__ import annotations

import argparse
import atexit
import logging
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DOT_PORT_FILE = PROJECT_ROOT / ".backend_port"
ENV_FILE = PROJECT_ROOT / ".env"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("launcher")

# ── Global state ──────────────────────────────────────────────
_backend_proc: subprocess.Popen | None = None
_frontend_proc: subprocess.Popen | None = None


# ── Helpers ───────────────────────────────────────────────────

def find_free_port() -> int:
    """Ask the OS for an ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def write_port_file(port: int) -> None:
    DOT_PORT_FILE.write_text(str(port), encoding="utf-8")
    logger.info("Port file written: %s → %d", DOT_PORT_FILE, port)


def remove_port_file() -> None:
    DOT_PORT_FILE.unlink(missing_ok=True)


def prefix_output(pipe, prefix: str):
    """Read lines from *pipe* and print them with *prefix*."""
    try:
        for line in iter(pipe.readline, ""):
            if line:
                print(f"{prefix} {line.rstrip()}")
    except Exception:
        pass
    finally:
        pipe.close()


def wait_for_backend(port: int, timeout: float = 15.0) -> bool:
    """Poll /health until the backend responds or *timeout* expires."""
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health", timeout=2
            )
            if resp.status == 200:
                logger.info("Backend health check passed")
                return True
        except Exception:
            pass
        time.sleep(0.5)
    logger.warning("Backend health check timed out after %.0fs", timeout)
    return False


def stop_process(proc: subprocess.Popen | None, name: str) -> None:
    """Gracefully stop *proc*; kill if it doesn't exit in 5 s."""
    if proc is None or proc.poll() is not None:
        return
    logger.info("Stopping %s (PID %d)...", name, proc.pid)
    if sys.platform == "win32":
        proc.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        logger.warning("%s did not exit; killing...", name)
        proc.kill()
        proc.wait()


def cleanup() -> None:
    """ATExit handler — stop frontend first, then backend."""
    global _frontend_proc, _backend_proc
    logger.info("Shutting down...")
    stop_process(_frontend_proc, "FRONTEND")
    stop_process(_backend_proc, "BACKEND")
    remove_port_file()


# ── Main ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI Desktop Pet Launcher")
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Backend port (default: 8000)",
    )
    parser.add_argument(
        "--no-frontend", action="store_true",
        help="Start backend only",
    )
    args = parser.parse_args()

    port = args.port
    is_ephemeral = False
    if port == 0:
        port = find_free_port()
        is_ephemeral = True
        logger.info("Using ephemeral port: %d", port)

    # Write port file (so frontend config can read it)
    write_port_file(port)

    # Register cleanup
    atexit.register(cleanup)

    # Handle Ctrl+C gracefully
    def _signal_handler(sig, frame):
        logger.info("Received signal %s, shutting down...", sig)
        cleanup()
        sys.exit(0)

    if sys.platform == "win32":
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
    else:
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

    # ── Start backend ──────────────────────────────────────────
    backend_cmd = [
        "python", "-m", "uvicorn",
        "backend.main:app",
        "--host", "127.0.0.1",
        "--port", str(port),
    ]
    if not is_ephemeral:
        backend_cmd.append("--reload")

    logger.info("Starting BACKEND on port %d...", port)
    global _backend_proc
    _backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    # ── Wait for backend ───────────────────────────────────────
    if not wait_for_backend(port, timeout=15):
        logger.error("Backend failed to start. Aborting.")
        cleanup()
        sys.exit(1)

    # ── Start frontend ─────────────────────────────────────────
    if args.no_frontend:
        logger.info("Frontend disabled via --no-frontend")
        _backend_proc.wait()
        return

    logger.info("Starting FRONTEND...")
    global _frontend_proc
    _frontend_proc = subprocess.Popen(
        ["python", "-u", "frontend/pet_window.py"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if _frontend_proc.stdout:
        import threading
        t = threading.Thread(target=prefix_output, args=(_frontend_proc.stdout, "[FRONTEND]"), daemon=True)
        t.start()

    # ── Monitor child processes ────────────────────────────────
    try:
        while True:
            # Check backend
            if _backend_proc.poll() is not None:
                logger.error(
                    "BACKEND exited unexpectedly (code %d). Stopping.",
                    _backend_proc.returncode,
                )
                cleanup()
                sys.exit(1)
            # Check frontend
            if _frontend_proc.poll() is not None:
                logger.error(
                    "FRONTEND exited unexpectedly (code %d). Stopping.",
                    _frontend_proc.returncode,
                )
                cleanup()
                sys.exit(1)
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Ctrl+C received, shutting down...")
    finally:
        cleanup()


if __name__ == "__main__":
    main()