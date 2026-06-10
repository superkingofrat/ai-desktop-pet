"""Provider abstract base — interface for all LLM providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


class BaseProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    def get_default_model(self) -> str:
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        ...
