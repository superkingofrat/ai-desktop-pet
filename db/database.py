"""SQLite database 鈥?connection, table creation, and session management."""

from __future__ import annotations

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger("assistant.db")


class Database:
    """Manages the SQLite database connection and schema creation."""

    def __init__(self, db_path: str | Path | None = None):
        from backend.core.config import settings
        self.db_path = Path(db_path) if db_path else settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    # 鈹€鈹€ Schema 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

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

    CREATE TABLE IF NOT EXISTS daily_reports (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        report_date TEXT UNIQUE NOT NULL,
        content     TEXT NOT NULL,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """

    # 鈹€鈹€ Public API 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def get_conn(self) -> sqlite3.Connection:
        """Return a new SQLite connection (row factory enabled)."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # 鈹€鈹€ Internals 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _init_tables(self) -> None:
        with self.get_conn() as conn:
            conn.executescript(self.SCHEMA_SQL)
        logger.info("Database ready: %s", self.db_path)

# ---------------------------------------------------------------------------
# Memory functions
# ---------------------------------------------------------------------------

def create_memory_table(db: Database) -> None:
    # Create the memory table if it does not already exist.
    with db.get_conn() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS memory (\n"
            "    id          INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "    user_id     INTEGER DEFAULT 1,\n"
            "    content     TEXT NOT NULL,\n"
            "    memory_type TEXT NOT NULL DEFAULT 'conversation',\n"
            "    timestamp   TEXT NOT NULL DEFAULT (datetime('now'))\n"
            ")"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_type \n"
            "ON memory(memory_type, timestamp)"
        )
    logger.info("Memory table ready")


def add_memory(
    db: Database,
    content: str,
    memory_type: str = "conversation",
) -> int:
    # Insert a memory record and return its new ID.
    with db.get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO memory (content, memory_type) VALUES (?, ?)",
            (content, memory_type),
        )
        return cur.lastrowid or 0


def get_recent_memories(
    db: Database,
    limit: int = 5,
    memory_type: str | None = None,
) -> list[dict]:
    # Return the most recent *limit* memories, optionally filtered by type.
    with db.get_conn() as conn:
        if memory_type:
            rows = conn.execute(
                "SELECT id, user_id, content, memory_type, timestamp "
                "FROM memory WHERE memory_type = ? "
                "ORDER BY id DESC LIMIT ?",
                (memory_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, user_id, content, memory_type, timestamp "
                "FROM memory ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in reversed(rows)]


def search_memories(db: Database, keyword: str) -> list[dict]:
    # Return all memories whose content contains *keyword*.
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT id, user_id, content, memory_type, timestamp "
            "FROM memory WHERE content LIKE ? "
            "ORDER BY id DESC",
            (f"%{keyword}%",),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Daily Report functions
# ---------------------------------------------------------------------------

def save_daily_report(db, report_date, content):
    with db.get_conn() as conn:
        cur = conn.execute(
            "INSERT OR REPLACE INTO daily_reports (report_date, content, created_at) "
            "VALUES (?, ?, datetime('now'))",
            (report_date, content),
        )
        return cur.lastrowid or 0


def get_daily_report(db, report_date):
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT id, report_date, content, created_at FROM daily_reports "
            "WHERE report_date = ?",
            (report_date,),
        ).fetchone()
    return dict(row) if row else None


def get_reports(db, start_date, end_date):
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT id, report_date, content, created_at FROM daily_reports "
            "WHERE report_date >= ? AND report_date <= ? "
            "ORDER BY report_date DESC",
            (start_date, end_date),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Daily Report functions
# ---------------------------------------------------------------------------

def save_daily_report(db, report_date, content):
    with db.get_conn() as conn:
        cur = conn.execute(
            "INSERT OR REPLACE INTO daily_reports (report_date, content, created_at) "
            "VALUES (?, ?, datetime('now'))",
            (report_date, content),
        )
        return cur.lastrowid or 0


def get_daily_report(db, report_date):
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT id, report_date, content, created_at FROM daily_reports "
            "WHERE report_date = ?",
            (report_date,),
        ).fetchone()
    return dict(row) if row else None


def get_reports(db, start_date, end_date):
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT id, report_date, content, created_at FROM daily_reports "
            "WHERE report_date >= ? AND report_date <= ? "
            "ORDER BY report_date DESC",
            (start_date, end_date),
        ).fetchall()
    return [dict(r) for r in rows]

