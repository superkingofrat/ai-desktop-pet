"""SQLite database — connection, table creation, and session management."""

from __future__ import annotations

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger("assistant.db")


class Database:
    """Manages the SQLite database connection and schema creation."""

    def __init__(self, db_path: str | Path = "data/assistant.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    # ── Schema ──────────────────────────────────────────────────

    SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS messages (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id  TEXT NOT NULL,
        role        TEXT NOT NULL,
        content     TEXT NOT NULL,
        timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    );

    CREATE TABLE IF NOT EXISTS user_profile (
        session_id  TEXT NOT NULL,
        key         TEXT NOT NULL,
        value       TEXT NOT NULL,
        PRIMARY KEY (session_id, key),
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    );

    CREATE INDEX IF NOT EXISTS idx_messages_session
        ON messages(session_id, id);
    """

    # ── Public API ──────────────────────────────────────────────

    def get_conn(self) -> sqlite3.Connection:
        """Return a new SQLite connection (row factory enabled)."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ── Internals ───────────────────────────────────────────────

    def _init_tables(self) -> None:
        with self.get_conn() as conn:
            conn.executescript(self.SCHEMA_SQL)
        logger.info("Database ready: %s", self.db_path)
