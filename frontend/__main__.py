"""launcher   python -m frontend [pet|chat|both]"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _python() -> str:
    """Return the Python executable path."""
    return sys.executable


def _run_pet() -> None:
    """Launch the pet window in-process."""
    from frontend.pet_window import main as pet_main
    pet_main()


def _run_chat() -> None:
    """Launch the chat window in-process."""
    from frontend.app import main as chat_main
    chat_main()


def _run_both() -> None:
    """Launch pet and chat as separate subprocesses."""
    root = Path(__file__).resolve().parent.parent
    env = {**{k: v for k, v in __import__("os").environ.items()}, "PYTHONPATH": str(root)}

    pet_proc = subprocess.Popen(
        [_python(), "-m", "frontend", "pet"],
        cwd=str(root), env=env,
    )
    chat_proc = subprocess.Popen(
        [_python(), "-m", "frontend", "chat"],
        cwd=str(root), env=env,
    )

    try:
        pet_proc.wait()
        chat_proc.wait()
    except KeyboardInterrupt:
        pet_proc.terminate()
        chat_proc.terminate()
        pet_proc.wait()
        chat_proc.wait()


def main() -> None:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lower() or "pet"

    if mode == "pet":
        _run_pet()
    elif mode == "chat":
        _run_chat()
    elif mode == "both":
        _run_both()
    else:
        print(f"Usage: python -m frontend [pet|chat|both]  (default: pet)")
        sys.exit(1)


if __name__ == "__main__":
    main()
