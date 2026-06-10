"""Database connection and session management."""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("assistant.db")


class Database:
    """Simple file-based database manager.

    Currently uses JSON files for storage; can be swapped to
    SQLite / PostgreSQL when needed.
    """

    def __init__(self, data_dir: str | Path = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, name: str) -> Path:
        """Return the full path for a named data file."""
        return self.data_dir / f"{name}.json"
