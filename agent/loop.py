"""Simplified Agent Loop — the core processing engine."""

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
    Simplified agent loop that:
    1. Takes a user message
    2. Builds context
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
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Process a user message and yield streaming updates.

        Yields dicts:
          - {"type": "thinking", "content": "..."}
          - {"type": "delta", "content": "..."}
          - {"type": "tool_call", "tool": "...", "args": {...}}
          - {"type": "tool_result", "tool": "...", "result": "..."}
          - {"type": "done", "content": "..."}
          - {"type": "error", "content": "..."}
        """
        tool_defs = self.tools.get_definitions()

        # Build messages
        system_prompt_text = personality or self.SYSTEM_PROMPT
        system_msg = {"role": "system", "content": system_prompt_text}
        messages = [system_msg]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": content})

        # Agent iteration loop (max 10 tool call rounds)
        max_iterations = 10
        iteration = 0
        final_content = None

        while iteration < max_iterations:
            iteration += 1
            yield {"type": "thinking", "content": "思考中..."}

            # Stream the LLM response
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
                # Add assistant message with tool calls
                assistant_msg = {"role": "assistant", "content": collected_delta or None}
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

                # Execute each tool call
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
                # No tool calls — this is the final response
                final_content = collected_delta
                yield {"type": "done", "content": final_content}
                return

        # Max iterations reached
        if final_content is None:
            final_content = collected_delta or "已完成处理，但没有更多需要回复的内容。"
            yield {"type": "done", "content": final_content}
