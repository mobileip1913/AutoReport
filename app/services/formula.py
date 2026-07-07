from __future__ import annotations

import ast
import operator
import re
from typing import Any

FIELD_PATTERN = re.compile(r"\{field:([a-zA-Z0-9_]+)\}")

ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
}


class FormulaError(Exception):
    pass


def extract_field_codes(expression: str) -> list[str]:
    return FIELD_PATTERN.findall(expression)


def _resolve_fields(expression: str, field_values: dict[str, float]) -> str:
    def replacer(match: re.Match[str]) -> str:
        code = match.group(1)
        if code not in field_values:
            raise FormulaError(f"字段 {code} 无可用数据")
        return str(field_values[code])

    return FIELD_PATTERN.sub(replacer, expression)


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_OPS:
        return ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_OPS:
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        if isinstance(node.op, ast.Div) and right == 0:
            raise FormulaError("除数不能为 0")
        return ALLOWED_OPS[type(node.op)](left, right)
    raise FormulaError("不支持的公式语法")


def evaluate_expression(expression: str, field_values: dict[str, float]) -> float:
    expr = expression.strip()
    if expr.startswith("="):
        expr = expr[1:].strip()
    if FIELD_PATTERN.fullmatch(expr):
        code = FIELD_PATTERN.match(expr).group(1)
        if code not in field_values:
            raise FormulaError(f"字段 {code} 无可用数据")
        return float(field_values[code])
    resolved = _resolve_fields(expr, field_values)
    if re.search(r"[a-zA-Z_]", resolved):
        raise FormulaError(f"公式中存在未解析字段: {resolved}")
    tree = ast.parse(resolved, mode="eval")
    return _safe_eval(tree)


def format_value(value: float | None, format_type: str) -> str:
    if value is None:
        return "-"
    if format_type == "currency":
        return f"¥{value:,.2f}"
    if format_type == "usd":
        return f"${value:,.2f}"
    if format_type == "percent":
        return f"{value * 100:.2f}%"
    if format_type == "integer":
        return f"{int(round(value)):,}"
    return f"{value:,.2f}"
