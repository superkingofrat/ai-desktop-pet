"""Tool registry — dynamic tool management with auto-discovery."""

from __future__ import annotations

from typing import Any

from agent.tools.base import BaseTool, TOOL_REGISTRY

# Re-export the global registry so callers can do:
#     from agent.tools.registry import TOOL_REGISTRY
__all__ = ["ToolRegistry", "TOOL_REGISTRY"]


class ToolRegistry:
    """Registry for agent tools.

    When created with ``auto_discover=True`` (the default), it
    automatically populates itself from the global ``TOOL_REGISTRY``
    that was built by ``BaseTool.__init_subclass__``.
    """

    def __init__(self, auto_discover: bool = True):
        self._tools: dict[str, BaseTool] = {}
        if auto_discover:
            self._tools.update(TOOL_REGISTRY)

    def register(self, tool: BaseTool) -> None:
        """Manually register a tool (e.g. for testing or dynamic addition)."""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Remove a tool by name."""
        self._tools.pop(name, None)

    def get(self, name: str) -> BaseTool | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def get_definitions(self) -> list[dict[str, Any]]:
        """Return OpenAI-compatible function-calling schemas for all tools."""
        return [t.to_schema() for t in self._tools.values()]

    async def execute(self, name: str, params: dict[str, Any]) -> str:
        """Execute the tool *name* with *params*."""
        tool = self._tools.get(name)
        if not tool:
            return (
                f"Error: Tool '{name}' not found. "
                f"Available: {', '.join(self._tools)}"
            )
        try:
            result = await tool.execute(**params)
            if isinstance(result, str) and result.startswith("Error"):
                return result
            return result
        except Exception as exc:
            return f"Error executing {name}: {exc}"

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())
