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


def mapping_source_file_keywords(mapping: FieldMapping) -> list[str]:
    """取数规则块直接绑定的来源文件 keyword（不含字段复用链）。"""
    keywords: set[str] = set()
    for p in sorted(mapping.parts or [], key=lambda x: x.sort_order):
        if p.ref_field_code:
            continue
        kw = (p.source_file_keyword or "").strip()
        if kw:
            keywords.add(kw)
        for s in p.sources or []:
            if not isinstance(s, dict):
                continue
            sk = (s.get("source_file_keyword") or "").strip()
            if sk:
                keywords.add(sk)
    return sorted(keywords)


def is_manual_line(mapping: FieldMapping) -> bool:
    return (mapping.line_type or "").lower() == "manual"


def is_per_order_line(mapping: FieldMapping) -> bool:
    """每单金额行：出报时 = per_order_amount × 单数（口径见 per_order_basis）。"""
    return (mapping.line_type or "").lower() == "per_order"


def is_ratio_line(mapping: FieldMapping) -> bool:
    """按比例行：出报时 = 复用字段(ratio_base_code) × ratio_percent%。"""
    return (mapping.line_type or "").lower() == "ratio"


# 每单金额单数口径
PER_ORDER_BASIS_VALID = "valid_orders"   # 当日去重有效订单数（下单口径）
PER_ORDER_BASIS_REVIEW = "review_orders"  # 刷单单数（不重复 Order ID）


def per_order_basis(mapping: FieldMapping) -> str:
    basis = (getattr(mapping, "per_order_basis", None) or "").strip()
    return PER_ORDER_BASIS_REVIEW if basis == PER_ORDER_BASIS_REVIEW else PER_ORDER_BASIS_VALID


def is_ref_compute_line(mapping: FieldMapping) -> bool:
    """日报行仅通过复用其他字段加减组合（parts 全是 ref_field_code）。"""
    parts = list(mapping.parts or [])
    if not parts:
        return False
    return all((getattr(p, "ref_field_code", None) or "").strip() for p in parts)


PLACEHOLDER_RULE_SUMMARY = "占位，导出后手工填写或上传文件"


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
    return field_display_type(mapping) == "fetch"


def field_display_type(mapping: FieldMapping, line_code: str | None = None) -> str:
    """日报字段展示分类：placeholder | review | sample | compute | fetch | per_order | ratio | formula。

    显式配置（每单金额/按比例/占位/取数或复用 parts）优先于 review/sample 等按 code 的启发判定，
    这样刷单物流费用等字段也能改用统一取数方式。
    """
    code = line_code or mapping_line_code(mapping)
    from app.services.meichong_rules import (
        MANUAL_FILL_LABELS,
        PENDING_FILE_CODES,
        REVIEW_IMPORT_CODES,
        SAMPLE_IMPORT_CODES,
    )
    label = mapping_label(mapping)
    # —— 显式配置优先 ——
    if is_per_order_line(mapping):
        return "per_order"
    if is_ratio_line(mapping):
        return "ratio"
    if is_manual_line(mapping):
        return "placeholder"
    if mapping.parts:
        return "compute" if is_ref_compute_line(mapping) else "fetch"
    # —— 无显式配置时，按 code / label 启发 ——
    if label in MANUAL_FILL_LABELS:
        return "placeholder"
    if code in REVIEW_IMPORT_CODES:
        return "review"
    if code in SAMPLE_IMPORT_CODES:
        return "sample"
    if code in PENDING_FILE_CODES:
        return "placeholder"
    if is_formula_line(mapping):
        return "formula"
    return "fetch"


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


_AGG_LABELS: dict[str, str] = {
    "sum": "求和",
    "count": "计数",
    "count_distinct": "去重计数",
    "sum_dedup": "去重求和",
    "max_dedup": "去重取最大",
    "avg": "平均值",
}


def _agg_label(agg: str | None) -> str:
    key = (agg or "sum").strip()
    return _AGG_LABELS.get(key, key)


def _resolve_file_label(keyword: str | None, file_labels: dict[str, str] | None) -> str:
    kw = (keyword or "").strip()
    if not kw:
        return ""
    labels = file_labels or {}
    return labels.get(kw) or labels.get(kw.lower()) or kw


def _source_loc(source: dict, file_labels: dict[str, str] | None) -> str:
    fl = _resolve_file_label(source.get("source_file_keyword"), file_labels)
    col = (source.get("column_header") or "").strip()
    if fl and col:
        return f"{fl}.{col}"
    return col or fl or "未指定"


def _resolve_field_label(code: str | None, field_labels: dict[str, str] | None) -> str:
    c = (code or "").strip()
    if not c:
        return ""
    labels = field_labels or {}
    return labels.get(c) or c


def build_field_labels_map(mappings, logical_fields) -> dict[str, str]:
    """字段 code → 展示名（逻辑字段名 + 报表行 label）。"""
    out: dict[str, str] = {}
    for lf in logical_fields or []:
        code = getattr(lf, "code", None) or ""
        name = getattr(lf, "name", None) or ""
        if code and name:
            out[code] = name
    for m in mappings or []:
        code = mapping_line_code(m)
        label = mapping_label(m)
        if code and label:
            out[code] = label
    return out


def part_rule_brief(
    part,
    file_labels: dict[str, str] | None = None,
    field_labels: dict[str, str] | None = None,
) -> str:
    """列表页规则摘要：订单.Order Amount · 去重求和（详情见配置弹窗）。"""
    ref = (getattr(part, "ref_field_code", None) or "").strip()
    if ref:
        return _resolve_field_label(ref, field_labels)

    sources = getattr(part, "sources", None) or []
    if sources:
        pieces: list[str] = []
        for i, src in enumerate(sources):
            loc = _source_loc(src, file_labels)
            pieces.append(f"+ {loc}" if i else loc)
        src_text = " ".join(pieces)
    else:
        src_text = _source_loc(
            {
                "source_file_keyword": getattr(part, "source_file_keyword", None),
                "column_header": getattr(part, "column_header", None),
            },
            file_labels,
        )

    return f"{src_text} · {_agg_label(getattr(part, 'aggregation', None))}"


def _iter_part_row_filters(part) -> list[dict]:
    """行筛选：优先各来源列上的 row_filters，兼容旧 part 级配置。"""
    sources = getattr(part, "sources", None) or []
    if sources:
        out: list[dict] = []
        for src in sources:
            if isinstance(src, dict):
                out.extend(src.get("row_filters") or [])
        if out:
            return out
    return list(getattr(part, "row_filters", None) or [])


def part_rule_hints(part) -> list[str]:
    """取数 part 规则摘要后缀：日期列、行筛选等。"""
    hints: list[str] = []
    date_col = (getattr(part, "date_filter_column", None) or "").strip()
    if date_col:
        hints.append(f"{date_col}=日报")
    for cond in _iter_part_row_filters(part):
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
    if getattr(part, "exclude_same_day_refund", False):
        adv.append("排除当日退单")
    if getattr(part, "join_to_orders", False):
        adv.append("关联主表")
    if getattr(part, "only_sample", False):
        adv.append("仅样品")
    if adv:
        hints.append("、".join(adv))
    return hints
