# -*- coding: utf-8 -*-
"""从生产 DDL 同步 Catalog 列映射（header_name = COMMENT，db_column = 生产列名）。

用法：
    python scripts/sync_production_catalog.py
    python scripts/sync_production_catalog.py --ds-id 4
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import CatalogColumn, CatalogFile, CatalogSheet, DataSource
from app.services.catalog_cleanup import cleanup_legacy_fact_catalog, ensure_production_fact_schema
from app.services.production_schema import PRODUCTION_TABLE_BY_SHEET, load_production_schema
from app.services.seed import MEICHONG_SOURCE_NAME
from scripts.etl.meichong_dataset import FILE_SHEETS, SHEET_SPECS, build_sheet_specs


def _upsert_catalog_file(db: Session, ds_id: int, keyword: str) -> CatalogFile:
    row = (
        db.query(CatalogFile)
        .filter(CatalogFile.data_source_id == ds_id, CatalogFile.keyword == keyword)
        .first()
    )
    if row:
        row.is_active = True
        return row
    row = CatalogFile(
        data_source_id=ds_id,
        keyword=keyword,
        file_label=keyword,
        file_name=f"{keyword}.xlsx",
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def _upsert_catalog_sheet(db: Session, file: CatalogFile, sheet_name: str, fact_table: str) -> CatalogSheet:
    row = (
        db.query(CatalogSheet)
        .filter(CatalogSheet.file_id == file.id, CatalogSheet.sheet_name == sheet_name)
        .first()
    )
    if row:
        row.fact_table = fact_table
        row.is_active = True
        return row
    row = CatalogSheet(file_id=file.id, sheet_name=sheet_name, fact_table=fact_table, is_active=True)
    db.add(row)
    db.flush()
    return row


def sync_catalog(db: Session, ds_id: int) -> None:
    schema = load_production_schema()
    sheet_specs = build_sheet_specs()
    for keyword, sheets in FILE_SHEETS:
        catalog_file = _upsert_catalog_file(db, ds_id, keyword)
        for sheet_name in sheets:
            spec = sheet_specs.get((keyword, sheet_name))
            if not spec:
                continue
            fact_table = spec["fact_table"]
            catalog_sheet = _upsert_catalog_sheet(db, catalog_file, sheet_name, fact_table)
            cols = schema.get(fact_table) or {}
            for db_col, header in cols.items():
                row = (
                    db.query(CatalogColumn)
                    .filter(CatalogColumn.sheet_id == catalog_sheet.id, CatalogColumn.db_column == db_col)
                    .first()
                )
                if row:
                    row.header_name = header
                    row.is_active = True
                else:
                    db.add(
                        CatalogColumn(
                            sheet_id=catalog_sheet.id,
                            header_name=header,
                            db_column=db_col,
                            column_aliases=[],
                            data_type="string",
                            is_active=True,
                        )
                    )
    db.commit()
    print(f"Catalog 已同步为生产列映射（data_source_id={ds_id}）。")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ds-id", type=int, default=None, help="数据源 ID，默认美宠")
    args = parser.parse_args()

    run_migrations()
    db = SessionLocal()
    try:
        if args.ds_id:
            ds = db.query(DataSource).filter(DataSource.id == args.ds_id).first()
        else:
            ds = db.query(DataSource).filter(DataSource.name == MEICHONG_SOURCE_NAME).first()
        if not ds:
            raise SystemExit("未找到数据源，请先运行 import_meichong 或 seed")
        cfg = dict(ds.config or {})
        cfg["fact_schema"] = "production"
        ds.config = cfg
        db.commit()
        sync_catalog(db, ds.id)
        cleanup_legacy_fact_catalog(db, ds.id)
    finally:
        db.close()


if __name__ == "__main__":
    main()
