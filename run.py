"""Unified launcher — starts backend on a free port and opens the frontend."""

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

# ── Paths ───────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
DOT_PORT_FILE = PROJECT_ROOT / ".backend_port"
ENV_FILE = PROJECT_ROOT / ".env"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("launcher")

# ── Global state ────────────────────────────────────────────────
_backend_proc: subprocess.Popen | None = None
_frontend_proc: subprocess.Popen | None = None


# ════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════

def find_free_port() -> int:
    """Ask the OS for an ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def write_port_file(port: int) -> None:
    DOT_PORT_FILE.write_text(str(port), encoding="utf-8")
    logger.info("Written .backend_port = %d", port)


def remove_port_file() -> None:
    if DOT_PORT_FILE.exists():
        DOT_PORT_FILE.unlink()
        logger.info("Removed .backend_port")


def cleanup():
    """atexit handler — kill child processes and remove port file."""
    global _backend_proc, _frontend_proc

    remove_port_file()

    if _frontend_proc is not None:
        logger.info("Stopping frontend (PID %d)...", _frontend_proc.pid)
        try:
            _frontend_proc.terminate()
            _frontend_proc.wait(timeout=3)
        except Exception:
            _frontend_proc.kill()
        _frontend_proc = None

    if _backend_proc is not None:
        logger.info("Stopping backend (PID %d)...", _backend_proc.pid)
        try:
            _backend_proc.terminate()
            _backend_proc.wait(timeout=5)
        except Exception:
            _backend_proc.kill()
        _backend_proc = None


def wait_for_backend(host: str, port: int, timeout: int = 10) -> bool:
    """Ping the /health endpoint until the backend is ready."""
    import urllib.request
    import json

    url = f"http://{host}:{port}/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = urllib.request.urlopen(url, timeout=2)
            if r.status == 200:
                data = json.loads(r.read())
                logger.info("Backend healthy: %s", data.get("tools", []))
                return True
        except Exception:
            pass
        time.sleep(0.5)
    logger.error("Backend did not start within %ds", timeout)
    return False


# ════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════

def main():
    global _backend_proc, _frontend_proc

    parser = argparse.ArgumentParser(description="AI Desktop Pet Launcher")
    parser.add_argument(
        "--mode", "-m",
        choices=["pet", "chat"],
        default="pet",
        help="Which frontend to launch (default: pet)",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=None,
        help="Backend port (default: auto-detect)",
    )
    args = parser.parse_args()

    # ── Resolve port ────────────────────────────────────────
    port = args.port if args.port else find_free_port()
    host = os.environ.get("BACKEND_HOST", "127.0.0.1")

    # Set environment for child processes
    env = os.environ.copy()
    env["BACKEND_HOST"] = host
    env["BACKEND_PORT"] = str(port)
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    if ENV_FILE.exists():
        env["DOTENV_FILE"] = str(ENV_FILE)

    # ── Write port file (for frontend/config.py) ────────────
    write_port_file(port)
    atexit.register(cleanup)

    # ── Start backend ───────────────────────────────────────
    python = sys.executable
    cmd = [
        python, "-m", "uvicorn", "backend.main:app",
        "--host", host,
        "--port", str(port),
        "--reload",
    ]
    logger.info("Starting backend on %s:%d ...", host, port)
    _backend_proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # ── Wait until healthy ──────────────────────────────────
    if not wait_for_backend(host, port):
        cleanup()
        sys.exit(1)

    # ── Start frontend ──────────────────────────────────────
    frontend_script = str(PROJECT_ROOT / "frontend" / "pet_window.py")
    if args.mode == "chat":
        frontend_script = str(PROJECT_ROOT / "frontend" / "app.py")

    logger.info("Starting frontend: %s", frontend_script)
    _frontend_proc = subprocess.Popen(
        [python, frontend_script],
        cwd=str(PROJECT_ROOT),
        env=env,
    )

    # ── Wait for frontend to finish, then clean up ──────────
    try:
        _frontend_proc.wait()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
