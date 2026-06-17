"""Agent Loop — core processing engine with conversation persistence and semantic cache."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from bus.queue import MessageBus
from agent.tools.registry import ToolRegistry
from providers.deepseek_provider import DeepSeekProvider
from db.database import Database, get_recent_memories

logger = logging.getLogger("assistant.agent.loop")


class AgentLoop:
    """
    Agent loop that:
    1. Takes a user message
    2. Builds context (system prompt + user profile + history)
    3. Checks semantic cache — hit → return directly
    4. Calls the LLM (streaming)
    5. Executes tool calls
    6. Stores result in cache
    7. Returns final response
    """

    SYSTEM_PROMPT = """你是一个有用的 AI 助手。
你可以使用工具来帮助用户完成任务。当用户请求需要调用工具时，请调用对应的工具。
当工具调用完成后，基于工具返回的结果，用自然语言回复用户。

在最终回复中，请用中文回复用户。"""

    def __init__(
        self,
        bus: MessageBus,
        provider: DeepSeekProvider,
        model: str | None = None,
    ):
        self.bus = bus
        self.provider = provider
        self.model = model or provider.get_default_model()
        self.tools = ToolRegistry()
        self._cached_tool_defs = None
        self._cache = None  # lazy-attached via process_message_stream

    def _get_tool_definitions(self):
        """Return cached tool definitions; rebuild on first call."""
        if self._cached_tool_defs is None:
            self._cached_tool_defs = self.tools.get_definitions()
        return self._cached_tool_defs

    async def process_message_stream(
        self,
        content: str,
        history: list[dict[str, Any]] | None = None,
        personality: str | None = None,
        *,
        session_id: str | None = None,
        conversation_manager: Any | None = None,
        semantic_cache: Any | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Process a user message and yield streaming updates.

        Parameters
        ----------
        content : str
            The user's current message.
        history : list[dict] | None
            In-memory message history (fallback when no DB is used).
        personality : str | None
            Override the system prompt.
        session_id : str | None
            When provided together with *conversation_manager*, history
            and user profile are loaded from the database instead of
            the in-memory *history* list.
        conversation_manager : ConversationManager | None
            Database-backed manager for persistence.
        semantic_cache : SemanticCache | None
            Cache for semantically similar queries (embedding-based).
        """
        tool_defs = self._get_tool_definitions()

        # ── Build messages list ──────────────────────────────────
        system_prompt_text = personality or self.SYSTEM_PROMPT
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt_text}
        ]

        if session_id and conversation_manager:
            # Inject user profile as a system-level hint
            profile = conversation_manager.get_user_profile(session_id)
            if profile:
                lines = [f"{k}: {v}" for k, v in profile.items()]
                messages.append({
                    "role": "system",
                    "content": "User Profile:\n" + "\n".join(lines),
                })

            # Load conversation history from DB
            db_history = conversation_manager.get_history(session_id, limit=10)
            messages.extend(db_history)
            try:
                from db.database import Database, get_recent_memories
                db = Database()
                conv = get_recent_memories(db, limit=5, memory_type="conversation")
                prefs = get_recent_memories(db, limit=100, memory_type="preference")
                lines = []
                if conv:
                    lines.append("--- \u6700\u8fd1\u5bf9\u8bdd ---")
                    for m in conv:
                        lines.append(m['content'])
                if prefs:
                    lines.append("--- \u7528\u6237\u504f\u597d ---")
                    for p in prefs:
                        lines.append(f"- {p['content']}")
                if lines:
                    messages.append({
                        "role": "system",
                        "content": "\u4ee5\u4e0b\u662f\u7528\u6237\u7684\u5386\u53f2\u5bf9\u8bdd\u548c\u504f\u597d\uff0c\u8bf7\u53c2\u8003\u8fd9\u4e9b\u4e0a\u4e0b\u6587\u6765\u56de\u7b54\uff1a\n" + "\n".join(lines),
                    })
            except Exception:
                pass
        elif history:
            messages.extend(history)

        messages.append({"role": "user", "content": content})

        # ── Semantic cache check ─────────────────────────────────
        if semantic_cache is not None:
            cached = semantic_cache.lookup(content)
            if cached is not None:
                logger.info("Cache hit for: %.50s", content)
                yield {"type": "thinking", "content": "命中缓存，直接返回结果..."}
                yield {"type": "done", "content": cached}
                if session_id and conversation_manager:
                    conversation_manager.add_message(session_id, "user", content)
                    conversation_manager.add_message(session_id, "assistant", cached)
                return

        # ── Agent iteration loop (max 10 tool-call rounds) ───────
        max_iterations = 10
        iteration = 0
        final_content: str | None = None
        pending_tool_calls = None

        while iteration < max_iterations:
            iteration += 1
            yield {"type": "thinking", "content": "思考中..."}

            collected_delta = ""
            pending_tool_calls = None

            async for chunk in self.provider.chat_stream(
                messages=messages,
                tools=tool_defs or None,
                model=self.model,
            ):
                if chunk["type"] == "delta":
                    collected_delta += chunk["content"]
                    yield {"type": "delta", "content": chunk["content"]}

                elif chunk["type"] == "tool_calls":
                    pending_tool_calls = chunk["tool_calls"]

                elif chunk["type"] == "done":
                    pass

                elif chunk["type"] == "error":
                    yield {"type": "error", "content": chunk["content"]}
                    return

            if pending_tool_calls:
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": collected_delta or None,
                }
                tool_call_dicts = []
                for tc in pending_tool_calls:
                    tool_call_dicts.append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"], ensure_ascii=False),
                        },
                    })
                    yield {"type": "tool_call", "tool": tc["name"], "args": tc["arguments"]}
                assistant_msg["tool_calls"] = tool_call_dicts
                messages.append(assistant_msg)

                for tc in pending_tool_calls:
                    result = await self.tools.execute(tc["name"], tc["arguments"])
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tc["name"],
                        "content": result,
                    })
                    yield {"type": "tool_result", "tool": tc["name"], "result": result}
            else:
                final_content = collected_delta
                yield {"type": "done", "content": final_content}

                # Persist
                if session_id and conversation_manager:
                    conversation_manager.add_message(session_id, "user", content)
                    conversation_manager.add_message(session_id, "assistant", final_content or "")

                # Cache the result (only cache non-tool final answers)
                if semantic_cache is not None and final_content:
                    semantic_cache.store(content, final_content)

                return

        # Max iterations reached
        if final_content is None:
            final_content = collected_delta or "已完成处理，但没有更多需要回复的内容。"
            yield {"type": "done", "content": final_content}

            if session_id and conversation_manager:
                conversation_manager.add_message(session_id, "user", content)
                conversation_manager.add_message(session_id, "assistant", final_content)

            if semantic_cache is not None and final_content and not pending_tool_calls:
                semantic_cache.store(content, final_content)
