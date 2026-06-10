"""Repository pattern — data access layer."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from db.database import Database

logger = logging.getLogger("assistant.db.repository")


class Repository:
    """Generic JSON-backed repository."""

    def __init__(self, db: Database, collection: str):
        self.file = db.path_for(collection)

    def _read(self) -> list[dict[str, Any]]:
        if not self.file.exists():
            return []
        try:
            return json.loads(self.file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            return []

    def _write(self, data: list[dict[str, Any]]) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def all(self) -> list[dict[str, Any]]:
        return self._read()

    def add(self, item: dict[str, Any]) -> None:
        items = self._read()
        items.append(item)
        self._write(items)

    def update(self, item_id: str, updates: dict[str, Any]) -> bool:
        items = self._read()
        for item in items:
            if item.get("id") == item_id:
                item.update(updates)
                self._write(items)
                return True
        return False

    def delete(self, item_id: str) -> bool:
        items = self._read()
        new_items = [i for i in items if i.get("id") != item_id]
        if len(new_items) == len(items):
            return False
        self._write(new_items)
        return True
