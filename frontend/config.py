"""Frontend configuration — resolves backend WebSocket URL."""

from __future__ import annotations

import os
from pathlib import Path


def _get_project_root() -> Path:
    """Return the project root directory (parent of frontend/)."""
    return Path(__file__).resolve().parent.parent


def get_backend_port() -> int:
    """Resolve the backend port using (in priority order):
    1. BACKEND_PORT environment variable
    2. .backend_port file (written by run.py)
    3. 8000 (default)
    """
    # 1) Environment variable
    env_port = os.environ.get("BACKEND_PORT")
    if env_port:
        try:
            return int(env_port)
        except (ValueError, TypeError):
            pass

    # 2) .backend_port file (written by run.py)
    dot_port = _get_project_root() / ".backend_port"
    if dot_port.exists():
        try:
            return int(dot_port.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            pass

    # 3) Default
    return 8000


def get_backend_host() -> str:
    """Resolve the backend host."""
    return os.environ.get("BACKEND_HOST", "127.0.0.1")


def get_ws_url(session_id: str = "pet-desktop") -> str:
    """Build WebSocket URL for the given session ID.

    Uses get_backend_port() and get_backend_host() to determine
    the correct address dynamically.
    """
    host = get_backend_host()
    port = get_backend_port()
    return f"ws://{host}:{port}/ws/chat?session_id={session_id}"


def get_chat_ws_url() -> str:
    """Shortcut for the default chat WebSocket URL (no session_id in path)."""
    host = get_backend_host()
    port = get_backend_port()
    return f"ws://{host}:{port}/ws/chat"
