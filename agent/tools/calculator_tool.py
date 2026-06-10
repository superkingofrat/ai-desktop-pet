"""Calculator tool — safely evaluate math expressions."""

from __future__ import annotations

import ast
import operator
from typing import Any

from agent.tools.base import BaseTool

# ── Whitelist of allowed AST node types for safe eval ────────────
_ALLOWED_NODES = (
    ast.Expr, ast.Expression, ast.BinOp, ast.UnaryOp,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd,
    ast.Constant,
    ast.Call, ast.Name, ast.Load,
)

# Map AST operators → Python operators
_OPS = {
    ast.Add:      operator.add,
    ast.Sub:      operator.sub,
    ast.Mult:     operator.mul,
    ast.Div:      operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod:      operator.mod,
    ast.Pow:      operator.pow,
    ast.USub:     operator.neg,
    ast.UAdd:     operator.pos,
}

# Whitelist of safe built-in functions
_SAFE_FUNCS = {
    "abs": abs, "round": round, "min": min, "max": max,
    "sum": sum, "int": int, "float": float,
    "len": len, "pow": pow,
}


def _safe_eval(expr: str) -> str:
    """Parse *expr* into an AST and evaluate only whitelisted nodes."""
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:
        return f"语法错误: {e}"

    # Validate that every node in the tree is whitelisted
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            return f"错误: 表达式中包含不允许的元素 '{type(node).__name__}'"

    def _eval(node: ast.AST):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"不支持的常量类型: {type(node.value).__name__}")
        if isinstance(node, ast.BinOp):
            op_func = _OPS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"不支持的操作符: {type(node.op).__name__}")
            return op_func(_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            op_func = _OPS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"不支持的操作符: {type(node.op).__name__}")
            return op_func(_eval(node.operand))
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("仅支持简单函数调用")
            func = _SAFE_FUNCS.get(node.func.id)
            if func is None:
                raise ValueError(f"不支持的函数: {node.func.id}")
            args = [_eval(a) for a in node.args]
            return func(*args)
        raise ValueError(f"不支持的表达式: {type(node).__name__}")

    try:
        result = _eval(tree.body)
        if isinstance(result, float):
            return f"{result:g}"
        return str(result)
    except Exception as e:
        return f"计算错误: {e}"


class CalculatorTool(BaseTool):
    """Safely evaluate mathematical expressions."""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return (
            "Evaluate a mathematical expression and return the result. "
            "Supports +, -, *, /, //, %, **, abs(), round(), min(), max(), "
            "and parentheses. Example inputs: '1+2*3', '(8+2)/5', '2**10'."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The mathematical expression to evaluate, e.g. '1+2*3'.",
                },
            },
            "required": ["expression"],
        }

    async def execute(self, **kwargs: Any) -> str:
        expr = kwargs.get("expression", "").strip()
        if not expr:
            return "Error: expression is required."
        return _safe_eval(expr)
