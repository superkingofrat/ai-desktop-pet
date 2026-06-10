"""Base class for agent tools — with auto-registration via __init_subclass__."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Abstract base class for all agent tools.

    Every subclass is automatically registered in the global TOOL_REGISTRY
    via the __init_subclass__ hook.
    """

    # ── Subclasses must override these ──────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name used in function calls (e.g. 'calculator')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Short description the LLM uses to decide when to call this tool."""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema describing the expected arguments."""
        ...

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool with the given keyword arguments.

        Returns a human-readable result string.
        """
        ...

    # ── Auto-registration ───────────────────────────────────────

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Catch every new BaseTool subclass and register it globally."""
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "_registered"):
            cls._registered = True
            _auto_register(cls)

    # ── Schema helper ────────────────────────────────────────────

    def to_schema(self) -> dict[str, Any]:
        """Convert this tool to an OpenAI-compatible function-call schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ---- Alias for backward compatibility ----
Tool = BaseTool


# ---- Global registry -------------------------------------------

TOOL_REGISTRY: dict[str, BaseTool] = {}


def _auto_register(tool_cls: type[BaseTool]) -> None:
    """Instantiate *tool_cls* once and store it under its ``name``.

    Called automatically by ``__init_subclass__`` whenever a concrete
    ``BaseTool`` subclass is imported for the first time.
    """
    instance = tool_cls()
    if instance.name in TOOL_REGISTRY:
        return  # already registered – first subclass wins
    TOOL_REGISTRY[instance.name] = instance
