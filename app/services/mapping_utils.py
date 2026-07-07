"""报表行（field_mapping）辅助：code / 展示名 / 分组。"""

from __future__ import annotations

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


def is_formula_line(mapping: FieldMapping) -> bool:
    if (mapping.line_type or "").lower() == "formula":
        return True
    if (mapping.line_type or "").lower() == "fetch":
        return False
    return bool((mapping.expression or "").strip()) and not mapping.parts and not (
        mapping.sheet_name and mapping.column_header
    )


def is_fetch_line(mapping: FieldMapping) -> bool:
    return not is_formula_line(mapping)


def default_expression(mapping: FieldMapping) -> str:
    if (mapping.expression or "").strip():
        return mapping.expression.strip()
    code = mapping_line_code(mapping)
    return f"{{field:{code}}}"


def slug_line_code(text: str, used: set[str]) -> str:
    base = _LINE_CODE_RE.sub("_", (text or "").lower().strip()).strip("_")[:40] or "line"
    if base[0].isdigit():
        base = f"r_{base}"
    name = base
    i = 2
    while name in used:
        name = f"{base}_{i}"
        i += 1
    used.add(name)
    return name
