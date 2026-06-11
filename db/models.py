"""SQLite-backed conversation manager — storage for sessions, messages, and user profiles.

Tables
------
- sessions(session_id, created_at)
- messages(id, session_id, role, content, timestamp)
- user_profile(session_id, key, value)
"""

from __future__ import annotations

import logging
from typing import Any

from db.database import Database

logger = logging.getLogger("assistant.db.models")


class ConversationManager:
    """Manages conversation history and user profiles via SQLite.

    Usage
    -----
        db = Database()
        cm = ConversationManager(db)

        cm.add_message("sess-1", "user", "Hello")
        history = cm.get_history("sess-1", limit=10)
        profile = cm.get_user_profile("sess-1")
    """

    def __init__(self, db: Database):
        self.db = db

    # ── Messages ────────────────────────────────────────────────

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Persist a single message.  Creates the session row if needed."""
        with self.db.get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sessions (session_id, created_at) "
                "VALUES (?, datetime('now'))",
                (session_id,),
            )
            conn.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )

    def get_history(
        self, session_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Return the most recent *limit* messages in chronological order."""
        with self.db.get_conn() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages "
                "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        # Reverse so oldest is first
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    # ── User Profile ────────────────────────────────────────────

    def get_user_profile(self, session_id: str) -> dict[str, str]:
        """Return all profile key-value pairs for a session."""
        with self.db.get_conn() as conn:
            rows = conn.execute(
                "SELECT key, value FROM user_profile WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        return {r["key"]: r["value"] for r in rows}

    def set_user_profile(
        self, session_id: str, key: str, value: str
    ) -> None:
        """Upsert a single profile entry."""
        with self.db.get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO user_profile (session_id, key, value) "
                "VALUES (?, ?, ?)",
                (session_id, key, value),
            )
