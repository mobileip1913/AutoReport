"""从 MySQL 生产事实表 `eb_overseas_tk_*` 加载聚合用行数据。"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.database import engine
from app.models import CatalogColumn, CatalogFile, CatalogSheet
from app.services.fact_row import FactRow
from app.services.production_fact import expand_production_record, resolve_production_store
from app.services.production_schema import is_production_fact_table


def load_fact_rows(db: Session, data_source_id: int, store_name: str) -> tuple[list[FactRow], dict[int, str]]:
    sheets = (
        db.query(CatalogSheet, CatalogFile)
        .join(CatalogFile, CatalogSheet.file_id == CatalogFile.id)
        .filter(
            CatalogFile.data_source_id == data_source_id,
            CatalogFile.is_active.is_(True),
            CatalogSheet.is_active.is_(True),
        )
        .all()
    )
    if not sheets:
        return [], {}

    import_file_names = {file.id: file.file_name for sheet, file in sheets}
    store_id, _ = resolve_production_store(db, data_source_id, store_name)
    if store_id is None:
        return [], import_file_names

    rows: list[FactRow] = []
    for sheet, file in sheets:
        if not is_production_fact_table(sheet.fact_table):
            continue
        active_cols = _active_columns(db, sheet)
        if not active_cols:
            continue
        table_cols = {c["name"] for c in inspect(engine).get_columns(sheet.fact_table)}
        select_cols = ["id"]
        if "extra_data" in table_cols:
            select_cols.append("extra_data")
        for c in active_cols:
            if c.db_column not in select_cols:
                select_cols.append(c.db_column)
        select_sql = ", ".join(f"`{c}`" for c in select_cols)
        sql = text(f"SELECT {select_sql} FROM `{sheet.fact_table}` WHERE store_id = :store_id")
        header_by_db = {c.db_column: c.header_name for c in active_cols}
        with engine.connect() as conn:
            result = conn.execute(sql, {"store_id": store_id})
            for record in result.mappings():
                row_data = expand_production_record(dict(record), sheet.fact_table, header_by_db)
                rows.append(
                    FactRow(
                        data_import_id=file.id,
                        sheet_name=sheet.sheet_name,
                        row_data=row_data,
                    )
                )
    return rows, import_file_names


def _active_columns(db: Session, sheet: CatalogSheet) -> list[CatalogColumn]:
    columns = (
        db.query(CatalogColumn)
        .filter(CatalogColumn.sheet_id == sheet.id, CatalogColumn.is_active.is_(True))
        .all()
    )
    if not columns:
        return []
    table_cols = {c["name"] for c in inspect(engine).get_columns(sheet.fact_table)}
    return [c for c in columns if c.db_column in table_cols]
