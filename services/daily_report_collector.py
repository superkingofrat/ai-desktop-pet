"""Daily report collector — fetches conversations and todos by date."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from db.database import Database

logger = logging.getLogger("assistant.report.collector")


def get_conversations_by_date(db: Database, date: str) -> list[dict[str, Any]]:
    """Return all user/assistant message pairs for a given date (YYYY-MM-DD)."""
    start = date + " 00:00:00"
    end = date + " 23:59:59"
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT session_id, role, content, timestamp "
            "FROM messages WHERE timestamp >= ? AND timestamp <= ? "
            "ORDER BY timestamp ASC",
            (start, end),
        ).fetchall()
    return [dict(r) for r in rows]


def get_todos_by_date(db: Database, date: str) -> list[dict[str, Any]]:
    """Return all todo-type memories for a given date (YYYY-MM-DD)."""
    start = date + " 00:00:00"
    end = date + " 23:59:59"
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT id, content, memory_type, timestamp "
            "FROM memory WHERE memory_type = 'todo' "
            "AND timestamp >= ? AND timestamp <= ? "
            "ORDER BY timestamp ASC",
            (start, end),
        ).fetchall()
    return [dict(r) for r in rows]


def collect_daily_data(db: Database, date: str) -> dict[str, Any]:
    """Collect all data needed for a daily report.

    Returns {"conversations": [...], "todos": [...]}
    """
    conversations = get_conversations_by_date(db, date)
    todos = get_todos_by_date(db, date)
    logger.info(
        "Collected %d conversations, %d todos for %s",
        len(conversations), len(todos), date,
    )
    return {"conversations": conversations, "todos": todos}
