"""将模板行定义同步到 field_mappings（报表配置）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import FieldMapping, FieldMappingPart, LogicalField
from app.services.formula import expression_to_ref_parts, extract_field_codes
from app.services.mapping_utils import is_formula_line, mapping_line_code, slug_line_code
from app.services.meichong_rules import MANUAL_FILL_LABELS, _LEGACY_MANUAL_LABELS


def _label_to_group(groups: list[tuple[str, list[str]]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for title, labels in groups:
        for label in labels:
            out[label] = title
    return out


def _apply_ref_parts(db: Session, mapping: FieldMapping, ref_parts: list[tuple[str, str]]) -> None:
    db.query(FieldMappingPart).filter(FieldMappingPart.mapping_id == mapping.id).delete()
    for idx, (ref_code, combine_op) in enumerate(ref_parts):
        db.add(
            FieldMappingPart(
                mapping_id=mapping.id,
                sort_order=idx,
                label=None,
                ref_field_code=ref_code,
                sheet_name="",
                column_header="",
                combine_op=combine_op,
                aggregation="sum",
            )
        )


def convert_formula_lines_to_fetch(db: Session, data_source_id: int) -> int:
    """把已有公式行改为「复用字段」取数行。"""
    n = 0
    for mapping in db.query(FieldMapping).filter(FieldMapping.data_source_id == data_source_id).all():
        if (mapping.line_type or "").lower() == "manual":
            continue
        if not is_formula_line(mapping):
            continue
        ref_parts = expression_to_ref_parts(mapping.expression or "")
        if not ref_parts:
            continue
        mapping.line_type = "fetch"
        mapping.expression = None
        _apply_ref_parts(db, mapping, ref_parts)
        n += 1
    if n:
        db.commit()
    return n


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
        if label in MANUAL_FILL_LABELS or label in _LEGACY_MANUAL_LABELS:
            canonical = label.replace("(估算)", "")
            mapping = by_label.get(canonical) or by_label.get(label)
            if not mapping and canonical in _LEGACY_MANUAL_LABELS:
                mapping = by_label.get(_LEGACY_MANUAL_LABELS[canonical])
            if not mapping:
                line_code = slug_line_code(canonical, used_codes)
                mapping = FieldMapping(
                    data_source_id=data_source_id,
                    line_code=line_code,
                    line_type="manual",
                    label=canonical,
                )
                db.add(mapping)
                db.flush()
                by_label[canonical] = mapping
                touched += 1
            mapping.line_type = "manual"
            mapping.label = canonical
            mapping.sort_order = sort_order
            mapping.expression = None
            mapping.format_type = fmt
            mapping.is_highlight = bool(highlight)
            mapping.report_group = label_group.get(canonical) or label_group.get(label)
            mapping.description = mapping.description or "导出 Excel 后由财务手工填写"
            continue

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
            mapping.expression = None
            mapping.format_type = fmt
            mapping.is_highlight = bool(highlight)
            mapping.report_group = label_group.get(label)
            if not only_missing or mapping.report_group:
                touched += 1
            continue

        ref_parts = expression_to_ref_parts(expr)
        if not ref_parts:
            continue

        mapping = by_label.get(label)
        if mapping and only_missing and mapping.report_group and mapping.parts:
            continue
        if not mapping:
            line_code = slug_line_code(label, used_codes)
            mapping = FieldMapping(
                data_source_id=data_source_id,
                line_code=line_code,
                line_type="fetch",
                label=label,
            )
            db.add(mapping)
            db.flush()
            by_label[label] = mapping
            by_line_code[line_code] = mapping
            touched += 1

        mapping.line_type = "fetch"
        mapping.label = label
        mapping.sort_order = sort_order
        mapping.expression = None
        mapping.format_type = fmt
        mapping.is_highlight = bool(highlight)
        mapping.report_group = label_group.get(label)
        _apply_ref_parts(db, mapping, ref_parts)
        touched += 1

    for m in db.query(FieldMapping).filter(FieldMapping.data_source_id == data_source_id).all():
        if m.label in _LEGACY_MANUAL_LABELS.values() and (m.line_type or "") != "manual":
            db.delete(m)
            touched += 1

    db.commit()
    convert_formula_lines_to_fetch(db, data_source_id)
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
