"""动态事实表 DDL 与写入。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

BASE_COLUMNS = {
    "id": "BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY",
    "data_source_id": "INT NOT NULL",
    "store_name": "VARCHAR(100) NOT NULL",
    "biz_date": "DATE NULL",
    "etl_batch_id": "INT NOT NULL",
    "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
}

SQLITE_BASE_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "data_source_id": "INTEGER NOT NULL",
    "store_name": "VARCHAR(100) NOT NULL",
    "biz_date": "DATE",
    "etl_batch_id": "INTEGER NOT NULL",
    "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
}


def _is_sqlite(engine: Engine) -> bool:
    return engine.dialect.name == "sqlite"


def _existing_columns(engine: Engine, table_name: str) -> set[str]:
    insp = inspect(engine)
    if not insp.has_table(table_name):
        return set()
    return {c["name"] for c in insp.get_columns(table_name)}


def ensure_fact_table(engine: Engine, table_name: str, data_columns: dict[str, str]) -> None:
    if not table_name.replace("_", "").isalnum():
        raise ValueError(f"非法表名: {table_name}")

    sqlite = _is_sqlite(engine)
    base = SQLITE_BASE_COLUMNS if sqlite else BASE_COLUMNS
    col_defs = dict(base)
    for col in data_columns:
        if col not in col_defs:
            col_defs[col] = "TEXT" if sqlite else data_columns[col]

    if not _existing_columns(engine, table_name):
        cols_sql = ", ".join(f"`{name}` {dtype}" for name, dtype in col_defs.items())
        if sqlite:
            ddl = f"CREATE TABLE IF NOT EXISTS `{table_name}` ({cols_sql})"
        else:
            ddl = (
                f"CREATE TABLE IF NOT EXISTS `{table_name}` ({cols_sql}, "
                f"KEY `idx_ds_store_date` (`data_source_id`,`store_name`,`biz_date`)"
                f") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
        with engine.begin() as conn:
            conn.execute(text(ddl))
        return

    existing = _existing_columns(engine, table_name)
    with engine.begin() as conn:
        for col, col_type in data_columns.items():
            if col in existing or col in base:
                continue
            alter_type = "TEXT" if sqlite else col_type
            conn.execute(text(f"ALTER TABLE `{table_name}` ADD COLUMN `{col}` {alter_type}"))


def clear_fact_rows(engine: Engine, table_name: str, data_source_id: int, store_name: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(f"DELETE FROM `{table_name}` WHERE data_source_id = :ds AND store_name = :store"),
            {"ds": data_source_id, "store": store_name},
        )


def clear_production_fact_rows(engine: Engine, table_name: str, store_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(f"DELETE FROM `{table_name}` WHERE store_id = :store_id"),
            {"store_id": store_id},
        )


def insert_fact_rows(
    engine: Engine,
    table_name: str,
    rows: list[dict[str, Any]],
    batch_size: int = 500,
) -> int:
    if not rows:
        return 0
    columns = sorted({key for row in rows for key in row})
    normalized = [{col: row.get(col) for col in columns} for row in rows]
    col_sql = ", ".join(f"`{c}`" for c in columns)
    placeholders = ", ".join(f":{c}" for c in columns)
    sql = text(f"INSERT INTO `{table_name}` ({col_sql}) VALUES ({placeholders})")
    inserted = 0
    with engine.begin() as conn:
        for i in range(0, len(normalized), batch_size):
            chunk = normalized[i : i + batch_size]
            conn.execute(sql, chunk)
            inserted += len(chunk)
    return inserted
