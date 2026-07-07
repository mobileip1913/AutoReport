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
        _add_column_if_missing(conn, "field_mapping_parts", "join_to_orders", "BOOLEAN DEFAULT 0")
        _add_column_if_missing(conn, "field_mapping_parts", "sources", "JSON")
        _add_column_if_missing(conn, "field_mapping_parts", "ref_field_code", "VARCHAR(50)")


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
