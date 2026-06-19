import os, py_compile

db_path = "E:/ai-assistant/db/database.py"
with open(db_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add daily_reports table
old = 'CREATE INDEX IF NOT EXISTS idx_messages_session\n        ON messages(session_id, id);\n    '
new = 'CREATE INDEX IF NOT EXISTS idx_messages_session\n        ON messages(session_id, id);\n\n    CREATE TABLE IF NOT EXISTS daily_reports (\n        id          INTEGER PRIMARY KEY AUTOINCREMENT,\n        report_date TEXT UNIQUE NOT NULL,\n        content     TEXT NOT NULL,\n        created_at  TEXT NOT NULL DEFAULT (datetime(\"now\"))\n    );\n    '

content = content.replace(old, new, 1)

# Add CRUD functions at end
extra = '''

# ---------------------------------------------------------------------------
# Daily Report functions
# ---------------------------------------------------------------------------

def save_daily_report(db, report_date, content):
    with db.get_conn() as conn:
        cur = conn.execute(
            "INSERT OR REPLACE INTO daily_reports (report_date, content, created_at) "
            "VALUES (?, ?, datetime(\"now\"))",
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
'''

content = content + extra

with open(db_path, "w", encoding="utf-8") as f:
    f.write(content)

py_compile.compile(db_path, doraise=True)
print("DB extended OK,", len(content), "bytes")
