"""从 MySQL 事实表加载聚合用行数据。"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.database import engine
from app.models import CatalogColumn, CatalogFile, CatalogSheet
from app.services.fact_row import FactRow


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
    rows: list[FactRow] = []

    for sheet, file in sheets:
        columns = (
            db.query(CatalogColumn)
            .filter(CatalogColumn.sheet_id == sheet.id, CatalogColumn.is_active.is_(True))
            .all()
        )
        if not columns:
            continue
        table_cols = {c["name"] for c in inspect(engine).get_columns(sheet.fact_table)}
        active_cols = [c for c in columns if c.db_column in table_cols]
        if not active_cols:
            continue
        db_cols = ["id"] + [c.db_column for c in active_cols]
        select_sql = ", ".join(f"`{c}`" for c in db_cols)
        sql = text(
            f"SELECT {select_sql} FROM `{sheet.fact_table}` "
            "WHERE data_source_id = :ds AND store_name = :store"
        )
        header_by_db = {c.db_column: c.header_name for c in active_cols}
        alias_map: dict[str, str] = {}
        for c in active_cols:
            alias_map[c.db_column] = c.header_name
            for alias in c.column_aliases or []:
                alias_map[c.db_column] = c.header_name

        with engine.connect() as conn:
            result = conn.execute(sql, {"ds": data_source_id, "store": store_name})
            for record in result.mappings():
                row_data: dict = {}
                for col in active_cols:
                    val = record.get(col.db_column)
                    row_data[col.header_name] = val
                    for alias in col.column_aliases or []:
                        row_data[alias] = val
                rows.append(
                    FactRow(
                        data_import_id=file.id,
                        sheet_name=sheet.sheet_name,
                        row_data=row_data,
                    )
                )
    return rows, import_file_names
