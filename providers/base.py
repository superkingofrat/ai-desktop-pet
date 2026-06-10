"""Provider abstract base — interface for all LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


class BaseProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    def get_default_model(self) -> str:
        """Return the default model identifier for this provider."""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream chat completion, yielding delta / tool_calls / done / error events."""
        ...

    async def generate_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Yield text *tokens* one by one (high-level streaming).

        Default implementation wraps ``chat_stream`` and extracts
        ``delta`` events.  Providers may override for tighter
        integration.
        """
        async for chunk in self.chat_stream(
            messages=messages, tools=tools, model=model, **kwargs
        ):
            if chunk.get("type") == "delta":
                yield chunk["content"]
            elif chunk.get("type") == "error":
                yield f"[ERROR: {chunk['content']}]"
                return
