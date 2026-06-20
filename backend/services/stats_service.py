"""Statistics service — aggregates data for the web dashboard."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from db.database import Database

logger = logging.getLogger(__name__)

TODOS_FILE = Path(__file__).parent.parent.parent / "data" / "todos.json"


def _date_range(days: int) -> list[str]:
    """Return a list of ISO date strings for the last *days* days."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]


def get_messages_by_day(db: Database, days: int) -> dict[str, Any]:
    """Return per-day message counts for the last *days* days."""
    dates = _date_range(days)
    start = dates[0]
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT DATE(timestamp) as d, COUNT(*) as c "
            "FROM messages WHERE DATE(timestamp) >= ? "
            "GROUP BY d ORDER BY d",
            (start,),
        ).fetchall()
    counts = {r["d"]: r["c"] for r in rows}
    return {"dates": dates, "counts": [counts.get(d, 0) for d in dates]}


def get_todo_stats() -> dict[str, Any]:
    """Return todo completion stats."""
    if not TODOS_FILE.exists():
        return {"done": 0, "total": 0}
    try:
        todos = json.loads(TODOS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"done": 0, "total": 0}
    total = len(todos)
    done = sum(1 for t in todos if t.get("done", False))
    return {"done": done, "total": total}


def get_reports_by_day(db: Database, days: int) -> dict[str, Any]:
    """Return daily report availability for the last *days* days."""
    dates = _date_range(days)
    start = dates[0]
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT report_date FROM daily_reports "
            "WHERE report_date >= ? ORDER BY report_date",
            (start,),
        ).fetchall()
    has = {r["report_date"] for r in rows}
    return {"dates": dates, "has_report": [d in has for d in dates]}


def get_focus_logs(db: Database, days: int) -> dict[str, Any]:
    """Return per-day focus-blocker trigger counts.

    Checks the *memory* table for 'focus_feedback' entries and
    also attempts to query a *focus_logs* table if it exists.
    """
    dates = _date_range(days)
    start = dates[0]
    counts: dict[str, int] = {}

    # Try the focus_logs table first
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                "SELECT DATE(created_at) as d, COUNT(*) as c "
                "FROM focus_logs WHERE DATE(created_at) >= ? "
                "GROUP BY d ORDER BY d",
                (start,),
            ).fetchall()
        counts = {r["d"]: r["c"] for r in rows}
    except Exception:
        pass

    if not counts:
        # Fallback: memory table focus feedback
        try:
            with db.get_conn() as conn:
                rows = conn.execute(
                    "SELECT DATE(timestamp) as d, COUNT(*) as c "
                    "FROM memory WHERE memory_type = 'focus_feedback' "
                    "AND DATE(timestamp) >= ? "
                    "GROUP BY d ORDER BY d",
                    (start,),
                ).fetchall()
            counts = {r["d"]: r["c"] for r in rows}
        except Exception:
            pass

    return {
        "dates": dates,
        "counts": [counts.get(d, 0) for d in dates],
    }


def get_stats(days: int = 7) -> dict[str, Any]:
    """Aggregate all stats for the last *days* days."""
    db = Database()
    try:
        return {
            "conversations": get_messages_by_day(db, days),
            "todos": get_todo_stats(),
            "focus": get_focus_logs(db, days),
            "reports": get_reports_by_day(db, days),
        }
    finally:
        pass
