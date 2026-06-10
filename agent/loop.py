"""Agent Loop — core processing engine with conversation persistence."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from bus.queue import MessageBus
from agent.tools.registry import ToolRegistry
from providers.deepseek_provider import DeepSeekProvider

logger = logging.getLogger("assistant.agent.loop")


class AgentLoop:
    """
    Agent loop that:
    1. Takes a user message
    2. Builds context (system prompt + user profile + history)
    3. Calls the LLM (streaming)
    4. Executes tool calls
    5. Returns final response
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

    async def process_message_stream(
        self,
        content: str,
        history: list[dict[str, Any]] | None = None,
        personality: str | None = None,
        *,
        session_id: str | None = None,
        conversation_manager: Any | None = None,
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

        Yields
        ------
        dicts with keys: type, content / tool / args / result / ...
        """
        tool_defs = self.tools.get_definitions()

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
        elif history:
            # Fallback: in-memory history list
            messages.extend(history)

        messages.append({"role": "user", "content": content})

        # ── Agent iteration loop (max 10 tool-call rounds) ───────
        max_iterations = 10
        iteration = 0
        collected_delta = ""
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
                # Append assistant message with tool-call metadata
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
                    yield {
                        "type": "tool_call",
                        "tool": tc["name"],
                        "args": tc["arguments"],
                    }
                assistant_msg["tool_calls"] = tool_call_dicts
                messages.append(assistant_msg)

                # Execute each tool call
                for tc in pending_tool_calls:
                    result = await self.tools.execute(tc["name"], tc["arguments"])
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tc["name"],
                        "content": result,
                    })
                    yield {
                        "type": "tool_result",
                        "tool": tc["name"],
                        "result": result,
                    }
            else:
                # No tool calls — this is the final response
                final_content = collected_delta
                yield {"type": "done", "content": final_content}

                # Persist user message + assistant response
                if session_id and conversation_manager:
                    conversation_manager.add_message(session_id, "user", content)
                    conversation_manager.add_message(
                        session_id, "assistant", final_content or ""
                    )
                return

        # Max iterations reached
        if final_content is None:
            final_content = collected_delta or "已完成处理，但没有更多需要回复的内容。"
            yield {"type": "done", "content": final_content}

            if session_id and conversation_manager:
                conversation_manager.add_message(session_id, "user", content)
                conversation_manager.add_message(
                    session_id, "assistant", final_content
                )
