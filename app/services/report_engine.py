from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import DataImport, DataRow, DataSource, FieldMapping, FieldMappingPart
from app.services.catalog_resolver import has_catalog
from app.services.fact_provider import load_fact_rows
from app.services.field_aggregator import aggregate_part, build_daily_context, combine_parts, resolve_part_value
from app.services.mapping_utils import is_fetch_line, mapping_line_code


def _to_number(value) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _resolve_column_value(row_data: dict, column_header: str, aliases: list) -> float | None:
    candidates = [column_header, *aliases]
    normalized_map = {str(k).strip(): v for k, v in row_data.items()}
    for candidate in candidates:
        key = str(candidate).strip()
        if key in normalized_map:
            return _to_number(normalized_map[key])
    return None


def aggregate_field_values(
    db: Session,
    data_source_id: int,
    report_date: str,
    store_name: str,
) -> tuple[dict[str, float], list[str]]:
    data_source = db.query(DataSource).filter(DataSource.id == data_source_id).first()
    daily_mode = bool(data_source and data_source.config)

    if has_catalog(db, data_source_id):
        rows, import_file_names = load_fact_rows(db, data_source_id, store_name)
        if not rows:
            return {}, [f"未找到 {store_name} 的事实数据，请先运行 ETL 导入"]
    else:
        if daily_mode:
            imports = (
                db.query(DataImport)
                .filter(
                    DataImport.data_source_id == data_source_id,
                    DataImport.store_name == store_name,
                )
                .order_by(DataImport.created_at.desc())
                .all()
            )
        else:
            imports = (
                db.query(DataImport)
                .filter(
                    DataImport.data_source_id == data_source_id,
                    DataImport.report_date == report_date,
                    DataImport.store_name == store_name,
                )
                .order_by(DataImport.created_at.desc())
                .all()
            )
        if not imports:
            return {}, [f"未找到 {store_name} 的导入数据"]
        import_ids = [i.id for i in imports]
        import_file_names = {i.id: i.file_name for i in imports}
        rows = db.query(DataRow).filter(DataRow.data_import_id.in_(import_ids)).all()

    context = None
    if daily_mode:
        context = build_daily_context(rows, data_source.config, report_date)

    mappings = (
        db.query(FieldMapping)
        .filter(FieldMapping.data_source_id == data_source_id)
        .all()
    )
    fetch_mappings = [m for m in mappings if is_fetch_line(m)]

    field_values: dict[str, float] = {}
    warnings: list[str] = []

    if daily_mode and data_source.config:
        from app.services.review_import import review_field_values
        same_day_ids = context.same_day_refund_order_ids if context else None
        field_values.update(review_field_values(data_source.config, same_day_ids))

    for _ in range(len(fetch_mappings) + 1):
        changed = False
        for mapping in fetch_mappings:
            code = mapping_line_code(mapping)
            display = mapping.label or (mapping.logical_field.name if mapping.logical_field else code)
            parts = sorted(mapping.parts, key=lambda p: p.sort_order)

            if parts:
                part_values = [
                    resolve_part_value(
                        p, rows, import_file_names, context, field_values,
                        db=db, data_source_id=data_source_id,
                    )
                    for p in parts
                ]
                new_val = combine_parts(parts, part_values)
                if field_values.get(code) != new_val:
                    changed = True
                field_values[code] = new_val
                if all(v == 0 for v in part_values) and not any(p.ref_field_code for p in parts):
                    warnings.append(f"字段「{display}」所有取数规则均未匹配到数据")
                continue

            if mapping.sheet_name and mapping.column_header:
                matched_values: list[float] = []
                for row in rows:
                    if row.sheet_name != mapping.sheet_name:
                        continue
                    value = _resolve_column_value(row.row_data, mapping.column_header, mapping.aliases or [])
                    if value is not None:
                        matched_values.append(value)
                if not matched_values:
                    warnings.append(f"字段「{display}」未取到数据")
                    new_val = 0.0
                elif mapping.aggregation == "count":
                    new_val = float(len(matched_values))
                elif mapping.aggregation == "avg":
                    new_val = sum(matched_values) / len(matched_values)
                else:
                    new_val = sum(matched_values)
                if field_values.get(code) != new_val:
                    changed = True
                field_values[code] = new_val
            else:
                if code not in field_values:
                    field_values[code] = 0.0
                    warnings.append(f"字段「{display}」未配置取数规则")
        if not changed:
            break

    return field_values, warnings


def _report_display_lines(all_lines: list[FieldMapping]) -> list[FieldMapping]:
    """仅输出已纳入报表结构的行（有排序或分组）；辅助取数字段不参与出报。"""
    return [
        line for line in all_lines
        if (line.sort_order or 0) > 0 or line.report_group
    ]


def generate_report_for_data_source(
    db: Session,
    data_source_id: int,
    report_date: str,
    store_name: str,
    is_test: bool = True,
):
    from app.models import ReportRun, ReportValue
    from app.services.formula import FormulaError, evaluate_expression, extract_field_codes, format_value
    from app.services.mapping_utils import default_expression, is_manual_line, mapping_label, mapping_line_code

    field_values, warnings = aggregate_field_values(db, data_source_id, report_date, store_name)

    all_lines = (
        db.query(FieldMapping)
        .filter(FieldMapping.data_source_id == data_source_id)
        .order_by(FieldMapping.sort_order, FieldMapping.id)
        .all()
    )
    report_lines = _report_display_lines(all_lines)
    if not report_lines:
        raise ValueError("该数据源尚未配置报表行，请先在「报表配置」页添加")

    for line in report_lines:
        if is_manual_line(line):
            continue
        expr = default_expression(line)
        for code in extract_field_codes(expr):
            field_values.setdefault(code, 0.0)

    run = ReportRun(
        template_id=None,
        data_source_id=data_source_id,
        report_date=report_date,
        store_name=store_name,
        is_test=is_test,
        status="warning" if warnings else "success",
    )
    db.add(run)
    db.flush()

    for line in report_lines:
        code = mapping_line_code(line)
        lbl = mapping_label(line)
        if is_manual_line(line):
            db.add(
                ReportValue(
                    report_run_id=run.id,
                    mapping_id=line.id,
                    line_code=code,
                    line_label=lbl,
                    expression="",
                    raw_value=None,
                    computed_raw_value=None,
                    display_value="",
                    is_overridden=False,
                    sort_order=line.sort_order or 0,
                    report_group=line.report_group,
                )
            )
            continue
        expr = default_expression(line)
        try:
            raw_value = evaluate_expression(expr, field_values)
            display = format_value(raw_value, line.format_type or "usd")
        except FormulaError as exc:
            raw_value = None
            display = f"错误: {exc}"
            run.status = "error"

        db.add(
            ReportValue(
                report_run_id=run.id,
                mapping_id=line.id,
                line_code=code,
                line_label=lbl,
                expression=expr,
                raw_value=raw_value,
                computed_raw_value=raw_value,
                display_value=display,
                is_overridden=False,
                sort_order=line.sort_order or 0,
                report_group=line.report_group,
            )
        )

    db.commit()
    db.refresh(run)
    run._warnings = warnings  # type: ignore[attr-defined]
    return run


def sync_run_missing_values(db: Session, run, data_source_id: int) -> int:
    """为已生成的 run 补全新增字段的 ReportValue（导出前调用）。"""
    from app.models import ReportValue
    from app.services.formula import FormulaError, evaluate_expression, extract_field_codes, format_value
    from app.services.mapping_utils import default_expression, is_manual_line, mapping_label, mapping_line_code

    existing = {
        v.mapping_id
        for v in db.query(ReportValue).filter(ReportValue.report_run_id == run.id).all()
        if v.mapping_id
    }
    all_lines = (
        db.query(FieldMapping)
        .filter(FieldMapping.data_source_id == data_source_id)
        .order_by(FieldMapping.sort_order, FieldMapping.id)
        .all()
    )
    report_lines = _report_display_lines(all_lines)
    missing = [line for line in report_lines if line.id not in existing]
    if not missing:
        return 0

    field_values, _ = aggregate_field_values(db, data_source_id, run.report_date, run.store_name)
    for line in report_lines:
        if not is_manual_line(line):
            expr = default_expression(line)
            for code in extract_field_codes(expr):
                field_values.setdefault(code, 0.0)

    added = 0
    for line in missing:
        code = mapping_line_code(line)
        lbl = mapping_label(line)
        if is_manual_line(line):
            db.add(
                ReportValue(
                    report_run_id=run.id,
                    mapping_id=line.id,
                    line_code=code,
                    line_label=lbl,
                    expression="",
                    raw_value=None,
                    computed_raw_value=None,
                    display_value="",
                    is_overridden=False,
                    sort_order=line.sort_order or 0,
                    report_group=line.report_group,
                )
            )
            added += 1
            continue
        expr = default_expression(line)
        try:
            raw_value = evaluate_expression(expr, field_values)
            display = format_value(raw_value, line.format_type or "usd")
        except FormulaError as exc:
            raw_value = None
            display = f"错误: {exc}"
        db.add(
            ReportValue(
                report_run_id=run.id,
                mapping_id=line.id,
                line_code=code,
                line_label=lbl,
                expression=expr,
                raw_value=raw_value,
                computed_raw_value=raw_value,
                display_value=display,
                is_overridden=False,
                sort_order=line.sort_order or 0,
                report_group=line.report_group,
            )
        )
        added += 1
    if added:
        db.commit()
    return added


def generate_report(
    db: Session,
    template,
    data_source_id: int,
    report_date: str,
    store_name: str,
    is_test: bool = True,
):
    """兼容旧模板出报；若数据源已有报表行配置则优先走新引擎。"""
    has_lines = (
        db.query(FieldMapping)
        .filter(FieldMapping.data_source_id == data_source_id, FieldMapping.sort_order > 0)
        .count()
    )
    if has_lines:
        run = generate_report_for_data_source(
            db, data_source_id, report_date, store_name, is_test=is_test
        )
        if template:
            run.template_id = template.id
            db.commit()
            db.refresh(run)
        return run

    from app.models import ReportRun, ReportValue, TemplateLine
    from app.services.formula import FormulaError, evaluate_expression, extract_field_codes, format_value

    field_values, warnings = aggregate_field_values(db, data_source_id, report_date, store_name)

    referenced: set[str] = set()
    for line in db.query(TemplateLine).filter(TemplateLine.template_id == template.id).all():
        referenced.update(extract_field_codes(line.expression))
    for code in referenced:
        field_values.setdefault(code, 0.0)

    run = ReportRun(
        template_id=template.id,
        data_source_id=data_source_id,
        report_date=report_date,
        store_name=store_name,
        is_test=is_test,
        status="warning" if warnings else "success",
    )
    db.add(run)
    db.flush()

    lines = (
        db.query(TemplateLine)
        .filter(TemplateLine.template_id == template.id)
        .order_by(TemplateLine.sort_order)
        .all()
    )

    for line in lines:
        try:
            raw_value = evaluate_expression(line.expression, field_values)
            display = format_value(raw_value, line.format_type)
        except FormulaError as exc:
            raw_value = None
            display = f"错误: {exc}"
            run.status = "error"

        db.add(
            ReportValue(
                report_run_id=run.id,
                line_label=line.label,
                expression=line.expression,
                raw_value=raw_value,
                display_value=display,
                sort_order=line.sort_order,
            )
        )

    db.commit()
    db.refresh(run)
    run._warnings = warnings  # type: ignore[attr-defined]
    return run
