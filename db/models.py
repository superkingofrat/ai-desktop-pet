"""Data models — Pydantic / dataclass schemas for persistence."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Conversation:
    """A single conversation session."""
    id: str
    title: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TodoItem:
    """A todo list item."""
    id: str
    task: str
    done: bool = False
    due_date: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
