"""Standalone utility helpers (not agent tools)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def read_json(path: Path) -> list[dict[str, Any]]:
    """Safely read a JSON file, returning [] on error."""
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, Exception):
        return []


def write_json(path: Path, data: list[dict[str, Any]]) -> None:
    """Write data to a JSON file with indentation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def timestamp() -> str:
    """ISO-8601 timestamp string."""
    return datetime.now().isoformat()
