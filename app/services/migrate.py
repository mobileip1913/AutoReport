"""数据库迁移：旧版单列映射 → 多规则 parts；补全新表。"""

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.database import engine
from app.models import Base, FieldMapping, FieldMappingPart, LogicalField


def run_migrations():
    Base.metadata.create_all(bind=engine)
    _ensure_mapping_columns()
    _ensure_part_columns()
    _ensure_data_source_columns()
    _ensure_report_run_columns()
    _ensure_field_mapping_report_columns()
    _ensure_report_value_columns()


def _add_column_if_missing(conn, table: str, column: str, ddl_type: str):
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns(table)}
    if column not in cols:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))


def _ensure_mapping_columns():
    insp = inspect(engine)
    if "field_mappings" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("field_mappings")}
    with engine.begin() as conn:
        if "description" not in cols:
            conn.execute(text("ALTER TABLE field_mappings ADD COLUMN description TEXT"))


def _ensure_part_columns():
    insp = inspect(engine)
    if "field_mapping_parts" not in insp.get_table_names():
        return
    with engine.begin() as conn:
        _add_column_if_missing(conn, "field_mapping_parts", "date_filter_column", "VARCHAR(100)")
        _add_column_if_missing(conn, "field_mapping_parts", "date_format", "VARCHAR(10)")
        _add_column_if_missing(conn, "field_mapping_parts", "row_filters", "JSON")
        _add_column_if_missing(conn, "field_mapping_parts", "exclude_sample", "BOOLEAN DEFAULT 0")
        _add_column_if_missing(conn, "field_mapping_parts", "exclude_review", "BOOLEAN DEFAULT 0")
        _add_column_if_missing(conn, "field_mapping_parts", "exclude_same_day_refund", "BOOLEAN DEFAULT 0")
        _add_column_if_missing(conn, "field_mapping_parts", "join_to_orders", "BOOLEAN DEFAULT 0")
        _add_column_if_missing(conn, "field_mapping_parts", "sources", "JSON")
        _add_column_if_missing(conn, "field_mapping_parts", "ref_field_code", "VARCHAR(50)")
        _add_column_if_missing(conn, "field_mapping_parts", "only_sample", "BOOLEAN DEFAULT 0")
        _add_column_if_missing(conn, "field_mapping_parts", "join_keys", "JSON")
        _add_column_if_missing(conn, "field_mapping_parts", "benchmark_keys", "JSON")


def _ensure_data_source_columns():
    insp = inspect(engine)
    if "data_sources" not in insp.get_table_names():
        return
    with engine.begin() as conn:
        _add_column_if_missing(conn, "data_sources", "config", "JSON")


def _ensure_report_run_columns():
    insp = inspect(engine)
    if "report_runs" not in insp.get_table_names():
        return
    with engine.begin() as conn:
        _add_column_if_missing(conn, "report_runs", "data_source_id", "INTEGER")
        _add_column_if_missing(conn, "report_runs", "template_id", "INTEGER")


def _ensure_field_mapping_report_columns():
    insp = inspect(engine)
    if "field_mappings" not in insp.get_table_names():
        return
    with engine.begin() as conn:
        _add_column_if_missing(conn, "field_mappings", "line_type", "VARCHAR(10)")
        _add_column_if_missing(conn, "field_mappings", "label", "VARCHAR(100)")
        _add_column_if_missing(conn, "field_mappings", "line_code", "VARCHAR(50)")
        _add_column_if_missing(conn, "field_mappings", "report_group", "VARCHAR(100)")
        _add_column_if_missing(conn, "field_mappings", "sort_order", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "field_mappings", "expression", "TEXT")
        _add_column_if_missing(conn, "field_mappings", "format_type", "VARCHAR(20)")
        _add_column_if_missing(conn, "field_mappings", "is_highlight", "BOOLEAN DEFAULT 0")
        _add_column_if_missing(conn, "field_mappings", "owner_id", "INTEGER")
        # logical_field_id 可空（SQLite 需重建列时跳过，新库由 create_all 处理）
        cols = {c["name"] for c in insp.get_columns("field_mappings")}
        if "logical_field_id" in cols:
            pass  # 已有列，nullable 仅对新 ORM 插入生效


def _ensure_report_value_columns():
    insp = inspect(engine)
    if "report_values" not in insp.get_table_names():
        return
    with engine.begin() as conn:
        _add_column_if_missing(conn, "report_values", "report_group", "VARCHAR(100)")
        _add_column_if_missing(conn, "report_values", "line_code", "VARCHAR(50)")
        _add_column_if_missing(conn, "report_values", "mapping_id", "INTEGER")
        _add_column_if_missing(conn, "report_values", "computed_raw_value", "FLOAT")
        _add_column_if_missing(conn, "report_values", "is_overridden", "BOOLEAN DEFAULT 0")


def ensure_logical_fields(db: Session) -> None:
    extra = [
        ("sku_discount", "SKU折扣", "每 SKU 行折扣，用 sum"),
        ("order_discount", "订单折扣", "订单级折扣，用 sum_dedup + Order ID"),
        ("settlement_credit", "结算调整(加)", "B 文件贷项"),
        ("settlement_charge", "结算扣费(减)", "B 文件借项"),
    ]
    for code, name, desc in extra:
        if not db.query(LogicalField).filter(LogicalField.code == code).first():
            db.add(LogicalField(code=code, name=name, description=desc))
    db.commit()


def migrate_legacy_mappings(db: Session) -> None:
    mappings = db.query(FieldMapping).all()
    for mapping in mappings:
        if mapping.parts:
            continue
        if not mapping.sheet_name or not mapping.column_header:
            continue
        db.add(
            FieldMappingPart(
                mapping_id=mapping.id,
                sort_order=0,
                label="默认规则",
                sheet_name=mapping.sheet_name,
                column_header=mapping.column_header,
                aliases=mapping.aliases or [],
                combine_op="add",
                aggregation=mapping.aggregation or "sum",
                dedup_keys=[],
            )
        )
    db.commit()


CANCELLED_LINE_CODES = frozenset({"mc_cancelled_amount", "mc_cancelled_order_count"})
CANCELLED_STATUS_VALUES = ("Canceled", "Cancelled")
CANCELLED_ROW_FILTER = {"column": "Order Status", "op": "in", "values": list(CANCELLED_STATUS_VALUES)}


def _strip_legacy_cancel_filters(filters: list | None) -> list:
    out: list = []
    for f in filters or []:
        col = f.get("column")
        op = f.get("op")
        if col == "Cancelled Time" and op == "nonempty":
            continue
        if col == "Order Status" and op in ("eq", "in", "contains", "not_contains"):
            continue
        out.append(f)
    return out


def migrate_cancelled_date_to_created(db: Session) -> None:
    """取消类指标：Created Time=日报日，Order Status 为 Canceled。"""
    from app.models import FieldMapping

    mappings = (
        db.query(FieldMapping)
        .filter(FieldMapping.line_code.in_(CANCELLED_LINE_CODES))
        .all()
    )
    changed = False
    for mapping in mappings:
        for part in mapping.parts:
            if part.date_filter_column != "Created Time":
                part.date_filter_column = "Created Time"
                part.date_format = part.date_format or "us"
                changed = True
            filters = _strip_legacy_cancel_filters(part.row_filters)
            filters.append(dict(CANCELLED_ROW_FILTER))
            if filters != (part.row_filters or []):
                part.row_filters = filters
                changed = True
    if changed:
        db.commit()


def repair_actual_order_count_parts(db: Session) -> None:
    """实际订单数：确保按 Created Time 过滤并排除样品/刷单。"""
    from app.models import FieldMapping

    mappings = (
        db.query(FieldMapping)
        .filter(FieldMapping.line_code == "mc_actual_order_count")
        .all()
    )
    changed = False
    for mapping in mappings:
        for part in mapping.parts:
            if not part.date_filter_column:
                part.date_filter_column = "Created Time"
                part.date_format = part.date_format or "us"
                changed = True
            if not part.exclude_sample:
                part.exclude_sample = True
                changed = True
            if not part.exclude_review:
                part.exclude_review = True
                changed = True
    if changed:
        db.commit()
