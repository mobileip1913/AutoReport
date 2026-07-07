"""报表行（field_mapping）辅助：code / 展示名 / 分组。"""

from __future__ import annotations

import hashlib
import re

from app.models import FieldMapping

_LINE_CODE_RE = re.compile(r"[^a-z0-9_]+")


def mapping_line_code(mapping: FieldMapping) -> str:
    if mapping.line_code:
        return mapping.line_code
    if mapping.logical_field and mapping.logical_field.code:
        return mapping.logical_field.code
    return f"line_{mapping.id}"


def mapping_label(mapping: FieldMapping) -> str:
    if mapping.label:
        return mapping.label
    if mapping.logical_field and mapping.logical_field.name:
        return mapping.logical_field.name
    return f"指标{mapping.id}"


def is_manual_line(mapping: FieldMapping) -> bool:
    return (mapping.line_type or "").lower() == "manual"


def is_formula_line(mapping: FieldMapping) -> bool:
    if is_manual_line(mapping):
        return False
    if (mapping.line_type or "").lower() == "formula":
        return True
    if (mapping.line_type or "").lower() == "fetch":
        return False
    return bool((mapping.expression or "").strip()) and not mapping.parts and not (
        mapping.sheet_name and mapping.column_header
    )


def is_fetch_line(mapping: FieldMapping) -> bool:
    return not is_formula_line(mapping) and not is_manual_line(mapping)


def is_report_line(mapping: FieldMapping) -> bool:
    """纳入日报结构的行（非基础取数字段）。"""
    return (mapping.sort_order or 0) > 0 or bool(mapping.report_group)


def report_display_mappings(mappings: list[FieldMapping]) -> list[FieldMapping]:
    lines = [m for m in mappings if is_report_line(m)]
    return sorted(lines, key=lambda m: (m.sort_order or 0, m.id))


def default_expression(mapping: FieldMapping) -> str:
    if (mapping.expression or "").strip():
        return mapping.expression.strip()
    code = mapping_line_code(mapping)
    return f"{{field:{code}}}"


def slug_line_code(text: str, used: set[str]) -> str:
    ascii_part = _LINE_CODE_RE.sub("_", (text or "").lower().strip()).strip("_")
    if not ascii_part or ascii_part in ("line", "r_line"):
        digest = hashlib.md5((text or "line").encode("utf-8")).hexdigest()[:8]
        base = f"rpt_{digest}"
    else:
        base = ascii_part[:40]
        if base[0].isdigit():
            base = f"r_{base}"
    name = base
    i = 2
    while name in used:
        name = f"{base}_{i}"
        i += 1
    used.add(name)
    return name


_ROW_FILTER_HINTS: dict[str, str] = {
    "nonempty": "非空",
    "empty": "为空",
    "eq": "=",
    "ne": "≠",
    "in": "属于",
    "not_in": "不属于",
    "contains": "包含",
    "not_contains": "不含",
    "starts_with": "开头",
    "ends_with": "结尾",
    "gt": ">",
    "gte": "≥",
    "lt": "<",
    "lte": "≤",
    "between": "介于",
}


def part_rule_hints(part) -> list[str]:
    """取数 part 规则摘要后缀：日期列、行筛选等。"""
    hints: list[str] = []
    date_col = (getattr(part, "date_filter_column", None) or "").strip()
    if date_col:
        hints.append(f"{date_col}=日报")
    for cond in getattr(part, "row_filters", None) or []:
        col = str(cond.get("column", "")).strip()
        op = cond.get("op", "eq")
        values = cond.get("values", [])
        if isinstance(values, (str, int, float)):
            values = [values]
        label = _ROW_FILTER_HINTS.get(op, op)
        if op in ("nonempty", "empty"):
            if col:
                hints.append(f"{col}{label}")
        elif op in ("eq", "ne", "contains", "not_contains", "starts_with", "ends_with", "gt", "gte", "lt", "lte"):
            val = str(values[0]).strip() if values else ""
            if col and val:
                hints.append(f"{col}{label}{val}")
        elif op in ("in", "not_in", "between") and col:
            vals = "、".join(str(v) for v in values[:3])
            if vals:
                hints.append(f"{col}{label}{vals}")
    adv: list[str] = []
    if getattr(part, "exclude_sample", False):
        adv.append("排除样品")
    if getattr(part, "exclude_review", False):
        adv.append("排除刷单")
    if getattr(part, "join_to_orders", False):
        adv.append("关联主表")
    if getattr(part, "only_sample", False):
        adv.append("仅样品")
    if adv:
        hints.append("、".join(adv))
    return hints
