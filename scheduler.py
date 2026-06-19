from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
import logging
from datetime import date

logger = logging.getLogger("assistant.scheduler")
scheduler = BackgroundScheduler()

def _generate_and_save():
    try:
        from services.daily_report_generator import generate_daily_report
        from db.database import Database, save_daily_report
        db = Database()
        today = date.today().isoformat()
        report = asyncio.run(generate_daily_report(db, today))
        save_daily_report(db, today, report)
        logger.info("Daily report saved: %s (%d chars)", today, len(report))
    except Exception as e:
        logger.error("Daily report failed: %s", e)

def start_scheduler():
    if scheduler.running: return
    scheduler.add_job(_generate_and_save, "cron", hour=22, minute=0, id="daily_report")
    scheduler.start()
    logger.info("Scheduler started - daily report at 22:00")

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")
