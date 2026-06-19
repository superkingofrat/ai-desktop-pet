import os, py_compile

path = "E:/ai-assistant/backend/api/routes.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

extra = '''

from fastapi import Query
from db.database import Database, get_daily_report, get_reports, save_daily_report
from services.daily_report_generator import generate_daily_report
import asyncio
from datetime import date


@router.get("/api/reports")
async def api_get_reports(
    date_str: str = Query(None, alias="date"),
    start: str = Query(None),
    end: str = Query(None),
):
    db = Database()
    if date_str:
        report = get_daily_report(db, date_str)
        return report or {"error": "No report for " + date_str}
    if start and end:
        return get_reports(db, start, end)
    return {"error": "Provide ?date= or ?start= + ?end="}


@router.post("/api/reports/generate")
async def api_generate_report(
    report_date: str = Query(None, alias="date"),
):
    db = Database()
    target = report_date or date.today().isoformat()
    content = await generate_daily_report(db, target)
    save_daily_report(db, target, content)
    return {"date": target, "content": content}
'''

content = content + extra

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

py_compile.compile(path, doraise=True)
print("Routes OK")
