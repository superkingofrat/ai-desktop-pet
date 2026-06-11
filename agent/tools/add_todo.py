"""Todo tool — saves todos to a local JSON file."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from agent.tools.base import BaseTool

logger = logging.getLogger("assistant.tools.todo")

TODOS_FILE = Path(__file__).parent.parent.parent / "data" / "todos.json"


class TodoTool(BaseTool):
    """Add / list tasks on a persistent todo list."""

    @property
    def name(self) -> str:
        return "todo"

    @property
    def description(self) -> str:
        return "Add a task to the todo list, or list pending tasks. Saves to a local JSON file."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list"],
                    "description": "'add' to create a new task, 'list' to show pending tasks.",
                },
                "task": {
                    "type": "string",
                    "description": "The task description (required when action='add').",
                },
                "due_date": {
                    "type": "string",
                    "description": "Optional due date in YYYY-MM-DD format.",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "add")

        if action == "list":
            return self._list_todos()

        # action == "add"
        task = kwargs.get("task", "").strip()
        if not task:
            return "Error: task is required when action='add'."

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

    def _list_todos(self) -> str:
        if not TODOS_FILE.exists():
            return "暂无待办事项。"

        try:
            todos = json.loads(TODOS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            return "暂无待办事项。"

        pending = [t for t in todos if not t.get("done", False)]
        if not pending:
            return "没有未完成的待办事项！"

        lines = ["📋 待办事项列表："]
        for t in pending:
            due = f" (截止: {t['due_date']})" if t.get("due_date") else ""
            lines.append(f"  - {t['task']}{due}")
        return "\n".join(lines)
