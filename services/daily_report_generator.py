"""AI daily report generator — calls LLM to produce a structured Markdown report."""

from __future__ import annotations

import json
import logging
from datetime import date as date_type
from typing import Any

from db.database import Database
from services.daily_report_collector import collect_daily_data

logger = logging.getLogger("assistant.report.generator")

DAILY_REPORT_PROMPT = """You are a smart assistant. Please generate a structured daily report based on today's conversations and to-do items.

Report format (Markdown):
# Daily Report YYYY-MM-DD
## Today's Conversation Summary
(summarize main topics, user sentiment and points of interest)
## Today's To-Do Completion Status
(list completed and uncompleted tasks with brief analysis)
## Suggestions for Tomorrow
(based on today's situation, provide 2-3 practical suggestions)

Conversation Records:
{conversations}

To-Do Items:
{todos}

Return the generated Markdown text."""


def _format_conversations(conversations: list[dict[str, Any]]) -> str:
    """Format conversation list into readable text."""
    if not conversations:
        return "(No conversations today)"
    lines = []
    for msg in conversations:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        timestamp = msg.get("timestamp", "")
        lines.append(f"[{timestamp}] {role}: {content[:200]}")
    return "\n".join(lines)


def _format_todos(todos: list[dict[str, Any]]) -> str:
    """Format todo list into readable text."""
    if not todos:
        return "(No to-do items today)"
    lines = []
    for t in todos:
        content = t.get("content", "")
        ts = t.get("timestamp", "")
        lines.append(f"- [{ts}] {content}")
    return "\n".join(lines)


async def generate_daily_report(
    db: Database,
    report_date: str | None = None,
) -> str:
    """Generate a daily report for *report_date* (YYYY-MM-DD, default today)."""
    if report_date is None:
        report_date = date_type.today().isoformat()

    # Collect data
    data = collect_daily_data(db, report_date)
    conversations = _format_conversations(data["conversations"])
    todos = _format_todos(data["todos"])

    # Build prompt
    prompt = DAILY_REPORT_PROMPT.format(
        conversations=conversations,
        todos=todos,
    )

    # Call LLM via provider
    from providers.deepseek_provider import DeepSeekProvider

    provider = DeepSeekProvider()
    model = provider.get_default_model()

    messages = [
        {"role": "system", "content": "You are a professional report writing assistant."},
        {"role": "user", "content": prompt},
    ]

    logger.info("Generating daily report for %s ...", report_date)
    try:
        result = await provider.generate(messages, model=model)
        report_text = result.strip()
        logger.info("Report generated: %d characters", len(report_text))
        return report_text
    except Exception as e:
        logger.error("Report generation failed: %s", e)
        return f"Error generating report: {e}"
