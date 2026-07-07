"""将模板行定义同步到 field_mappings（报表配置）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import FieldMapping, LogicalField
from app.services.formula import extract_field_codes
from app.services.mapping_utils import mapping_line_code, slug_line_code


def _label_to_group(groups: list[tuple[str, list[str]]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for title, labels in groups:
        for label in labels:
            out[label] = title
    return out


def sync_report_lines(
    db: Session,
    data_source_id: int,
    template_lines: list[tuple],
    template_groups: list[tuple[str, list[str]]],
    *,
    only_missing: bool = False,
) -> int:
    """把 template_lines 合并写入 field_mappings，返回新增/更新行数。"""
    label_group = _label_to_group(template_groups)
    field_map = {f.code: f for f in db.query(LogicalField).all()}
    existing = {
        m.id: m
        for m in db.query(FieldMapping).filter(FieldMapping.data_source_id == data_source_id).all()
    }
    by_line_code: dict[str, FieldMapping] = {}
    by_label: dict[str, FieldMapping] = {}
    for m in existing.values():
        code = mapping_line_code(m)
        by_line_code[code] = m
        if m.label:
            by_label[m.label] = m
        if m.logical_field and m.logical_field.code:
            by_line_code[m.logical_field.code] = m

    used_codes = {mapping_line_code(m) for m in existing.values() if mapping_line_code(m)}
    touched = 0

    for sort_order, label, expr, fmt, highlight in template_lines:
        field_codes = extract_field_codes(expr)
        simple_fetch = len(field_codes) == 1 and expr.strip() == f"{{field:{field_codes[0]}}}"

        if simple_fetch:
            mc_code = field_codes[0]
            mapping = by_line_code.get(mc_code)
            if mapping and only_missing and mapping.report_group:
                continue
            if not mapping:
                lf = field_map.get(mc_code)
                mapping = FieldMapping(
                    data_source_id=data_source_id,
                    logical_field_id=lf.id if lf else None,
                    line_code=mc_code,
                    line_type="fetch",
                    label=label,
                )
                db.add(mapping)
                db.flush()
                by_line_code[mc_code] = mapping
                by_label[label] = mapping
                touched += 1
            mapping.label = label
            mapping.line_code = mc_code
            mapping.line_type = "fetch"
            mapping.sort_order = sort_order
            mapping.expression = expr
            mapping.format_type = fmt
            mapping.is_highlight = bool(highlight)
            mapping.report_group = label_group.get(label)
            if not only_missing or mapping.report_group:
                touched += 1
            continue

        # 公式行或多字段表达式
        mapping = by_label.get(label)
        if mapping and mapping.line_type == "fetch" and mapping.logical_field:
            # 已有取数行，仅更新展示/分组，不改 line_type
            mapping.label = label
            mapping.sort_order = sort_order
            mapping.format_type = fmt
            mapping.is_highlight = bool(highlight)
            mapping.report_group = label_group.get(label)
            touched += 1
            continue

        if mapping and only_missing and mapping.expression == expr:
            continue
        if not mapping:
            line_code = slug_line_code(label, used_codes)
            mapping = FieldMapping(
                data_source_id=data_source_id,
                line_code=line_code,
                line_type="formula",
                label=label,
            )
            db.add(mapping)
            db.flush()
            by_label[label] = mapping
            by_line_code[line_code] = mapping
            touched += 1
        mapping.line_type = "formula"
        mapping.label = label
        mapping.sort_order = sort_order
        mapping.expression = expr
        mapping.format_type = fmt
        mapping.is_highlight = bool(highlight)
        mapping.report_group = label_group.get(label)

    db.commit()
    return touched


def backfill_mapping_line_codes(db: Session) -> int:
    """为旧映射补 line_code / label / line_type。"""
    n = 0
    for m in db.query(FieldMapping).all():
        changed = False
        if not m.line_code and m.logical_field and m.logical_field.code:
            m.line_code = m.logical_field.code
            changed = True
        if not m.label and m.logical_field:
            m.label = m.logical_field.name
            changed = True
        if not m.line_type:
            m.line_type = "fetch"
            changed = True
        if changed:
            n += 1
    if n:
        db.commit()
    return n
