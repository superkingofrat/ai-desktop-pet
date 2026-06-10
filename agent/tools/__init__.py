"""Agent tool system — base class, registry, and built-in tools.

Usage
-----
    from agent.tools import TOOL_REGISTRY, ToolRegistry

    # All BaseTool subclasses are auto-registered on import.
    print(TOOL_REGISTRY)          # {"calculator": <...>, "weather": <...>, "todo": <...>}

    # Create a per-agent snapshot:
    registry = ToolRegistry()     # auto-populated from TOOL_REGISTRY
    schema_list = registry.get_definitions()
"""

from __future__ import annotations

# ── Trigger auto-registration by importing every tool module ────
# Each *.py file that defines a BaseTool subclass fires
# __init_subclass__() → _auto_register() as soon as Python imports it.

from agent.tools import add_todo          # noqa: F401 — triggers TodoTool
from agent.tools import calculator_tool   # noqa: F401 — triggers CalculatorTool
from agent.tools import weather_tool      # noqa: F401 — triggers WeatherTool

# ── Make the tool classes directly importable ───────────────────
from agent.tools.add_todo import TodoTool                # noqa: F401
from agent.tools.calculator_tool import CalculatorTool   # noqa: F401
from agent.tools.weather_tool import WeatherTool         # noqa: F401

# ── Convenience re-exports ──────────────────────────────────────
from agent.tools.base import BaseTool, TOOL_REGISTRY, Tool   # noqa: F401
from agent.tools.registry import ToolRegistry                # noqa: F401

__all__ = [
    "BaseTool",
    "Tool",
    "TOOL_REGISTRY",
    "ToolRegistry",
    "TodoTool",
    "CalculatorTool",
    "WeatherTool",
]
