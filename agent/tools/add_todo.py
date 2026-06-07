"""Add Todo tool — saves todos to a local JSON file."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from agent.tools.base import Tool

logger = logging.getLogger("assistant.tools.add_todo")

TODOS_FILE = Path(__file__).parent.parent.parent / "data" / "todos.json"


class AddTodoTool(Tool):
    """Add a task to the todo list."""

    @property
    def name(self) -> str:
        return "add_todo"

    @property
    def description(self) -> str:
        return "Add a task to the todo list. Saves to a local JSON file."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task description.",
                },
                "due_date": {
                    "type": "string",
                    "description": "Optional due date in YYYY-MM-DD format.",
                },
            },
            "required": ["task"],
        }

    async def execute(self, **kwargs: Any) -> str:
        task = kwargs.get("task", "").strip()
        if not task:
            return "Error: task is required."

        due_date = kwargs.get("due_date", "").strip() or None

        todo = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "task": task,
            "due_date": due_date,
            "created_at": datetime.now().isoformat(),
            "done": False,
        }

        TODOS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if TODOS_FILE.exists():
            try:
                todos = json.loads(TODOS_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, Exception):
                todos = []
        else:
            todos = []

        todos.append(todo)
        TODOS_FILE.write_text(
            json.dumps(todos, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info("Added todo: %s (due: %s)", task, due_date or "none")
        msg = f"已添加待办事项: {task}"
        if due_date:
            msg += f" (截止日期: {due_date})"
        return msg
