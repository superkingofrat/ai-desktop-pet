"""DeepSeek LLM provider with streaming support."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("assistant.providers.deepseek")


@dataclass
class ToolCallRequest:
    """A tool call request from the LLM."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str | None = None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class DeepSeekProvider:
    """
    LLM provider using DeepSeek API (OpenAI-compatible).

    Supports both non-streaming (function calling) and
    streaming (text-only) responses.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def get_default_model(self) -> str:
        return self.model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Non-streaming chat completion with function calling support."""
        kwargs: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"

        try:
            response = await self.client.chat.completions.create(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return LLMResponse(content=f"Error calling LLM: {e}", finish_reason="error")

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Streaming chat completion.

        Yields dicts with keys:
          - type: "delta" | "tool_calls" | "done" | "error"
          - content / tool_calls / finish_reason
        """
        kwargs: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            stream = await self.client.chat.completions.create(**kwargs)

            tool_calls_acc: dict[int, dict] = {}
            content_parts: list[str] = []

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                finish_reason = chunk.choices[0].finish_reason if chunk.choices else None

                if delta is None:
                    if finish_reason:
                        yield {"type": "done", "finish_reason": finish_reason}
                    continue

                # Text content
                if delta.content:
                    content_parts.append(delta.content)
                    yield {"type": "delta", "content": delta.content}

                # Tool calls
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {
                                "id": tc.id or "",
                                "name": tc.function.name if tc.function else "",
                                "arguments": "",
                            }
                        if tc.function and tc.function.arguments:
                            tool_calls_acc[idx]["arguments"] += tc.function.arguments

                if finish_reason:
                    yield {"type": "done", "finish_reason": finish_reason}

            # If tool calls were accumulated, yield them
            if tool_calls_acc:
                tool_calls = []
                for idx in sorted(tool_calls_acc.keys()):
                    tc = tool_calls_acc[idx]
                    try:
                        args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    except json.JSONDecodeError:
                        args = {}
                    tool_calls.append({
                        "id": tc["id"],
                        "name": tc["name"],
                        "arguments": args,
                    })
                yield {"type": "tool_calls", "tool_calls": tool_calls}

        except Exception as e:
            logger.error("LLM stream failed: %s", e)
            yield {"type": "error", "content": f"Stream error: {e}"}

    async def generate_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Higher-level streaming: yield ``delta``, ``tool_calls``, ``done``, ``error`` events.

        Differs from ``chat_stream`` only in that it is an official
        part of the ``BaseProvider`` interface and includes additional
        metadata in the ``done`` event.
        """
        full_text = ""
        final_tool_calls = None

        async for chunk in self.chat_stream(
            messages=messages, tools=tools, model=model, **kwargs
        ):
            if chunk["type"] == "delta":
                full_text += chunk["content"]
                yield chunk
            elif chunk["type"] == "tool_calls":
                final_tool_calls = chunk["tool_calls"]
                yield chunk
            elif chunk["type"] == "done":
                yield {"type": "done", "content": full_text, "finish_reason": chunk.get("finish_reason")}
            elif chunk["type"] == "error":
                yield chunk
                return

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse a non-streaming response."""
        choice = response.choices[0]
        message = choice.message
        finish_reason = choice.finish_reason

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCallRequest(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))

        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=finish_reason or "stop",
            usage=usage,
        )
