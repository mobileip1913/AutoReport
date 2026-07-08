# -*- coding: utf-8 -*-
"""从 files/ 中美宠 Excel 导入 Catalog + 生产事实表 `eb_overseas_tk_*`。

用法（项目根目录、已配置 .env DATABASE_URL）：
    python scripts/apply_production_ddl.py
    python scripts/apply_production_store.py
    python scripts/import_meichong.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, engine
from app.models import CatalogColumn, CatalogFile, CatalogSheet, DataSource, EtlBatch, Store
from app.services.catalog_cleanup import cleanup_legacy_fact_catalog, ensure_production_fact_schema
from app.services.excel_reader import read_sheet_rows
from app.services.fact_storage import clear_production_fact_rows, insert_fact_rows
from app.services.meichong_rules import MEICHONG_CONFIG, apply_meichong_rules
from app.services.migrate import ensure_logical_fields, run_migrations
from app.services.production_fact import (
    excel_record_to_production_row,
    is_valid_data_row,
    resolve_production_store,
)
from app.services.production_schema import header_to_db_column, load_production_schema
from app.services.production_store import sync_store_production_ids
from app.services.seed import MEICHONG_STORE, ensure_meichong_datasource
from scripts.etl.meichong_dataset import FILE_SHEETS, REQUIRED_COLUMNS, SHEET_SPECS


def _match_keyword(file_name: str) -> str | None:
    for keyword, _ in FILE_SHEETS:
        if keyword in file_name:
            return keyword
    return None


def _match_sheets(file_name: str) -> set[str] | None:
    for keyword, sheets in FILE_SHEETS:
        if keyword in file_name:
            return sheets
    return None


def _ensure_store(db: Session, ds: DataSource) -> Store:
    store = db.query(Store).filter(Store.data_source_id == ds.id).first()
    cfg = dict(ds.config or MEICHONG_CONFIG)
    prod_id = cfg.get("production_store_id")
    shop_code = cfg.get("shop_code")
    if store:
        if prod_id is not None:
            store.production_store_id = int(prod_id)
        if shop_code:
            store.shop_code = shop_code
        db.commit()
        return store
    store = Store(
        name=MEICHONG_STORE,
        platform="TikTok Shop",
        data_source_id=ds.id,
        production_store_id=int(prod_id) if prod_id is not None else None,
        shop_code=shop_code,
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    return store


def _upsert_catalog_file(db: Session, ds_id: int, keyword: str, file_name: str) -> CatalogFile:
    row = (
        db.query(CatalogFile)
        .filter(CatalogFile.data_source_id == ds_id, CatalogFile.keyword == keyword)
        .first()
    )
    if row:
        row.file_name = file_name
        row.file_label = keyword
        row.is_active = True
        return row
    row = CatalogFile(
        data_source_id=ds_id,
        keyword=keyword,
        file_label=keyword,
        file_name=file_name,
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


def _upsert_catalog_columns(
    db: Session, sheet: CatalogSheet, headers: list[str], fact_table: str
) -> dict[str, CatalogColumn]:
    schema = load_production_schema()
    ddl_cols = schema.get(fact_table) or {}
    header_to_db = {comment: col for col, comment in ddl_cols.items()}
    mapping: dict[str, CatalogColumn] = {}
    for header in headers:
        if not header:
            continue
        db_col = header_to_db.get(header) or header_to_db_column(fact_table, header)
        if not db_col:
            continue
        row = (
            db.query(CatalogColumn)
            .filter(CatalogColumn.sheet_id == sheet.id, CatalogColumn.db_column == db_col)
            .first()
        )
        if row:
            row.header_name = header
            row.is_active = True
        else:
            row = CatalogColumn(
                sheet_id=sheet.id,
                header_name=header,
                db_column=db_col,
                column_aliases=[],
                data_type="string",
                is_active=True,
            )
            db.add(row)
        mapping[header] = row
    db.flush()
    return mapping


def _import_sheet(
    db: Session,
    ds_id: int,
    store_name: str,
    batch_id: int,
    path: Path,
    keyword: str,
    sheet_name: str,
) -> int:
    spec = SHEET_SPECS.get((keyword, sheet_name))
    if not spec:
        print(f"  [skip] 未配置 Sheet: {keyword}/{sheet_name}")
        return 0

    fact_table = spec["fact_table"]
    store_id, shop_code = resolve_production_store(db, ds_id, store_name)
    if store_id is None:
        raise RuntimeError("未配置 production_store_id，请运行 scripts/apply_production_store.py")

    catalog_file = _upsert_catalog_file(db, ds_id, keyword, path.name)
    catalog_sheet = _upsert_catalog_sheet(db, catalog_file, sheet_name, fact_table)

    excel_headers, records = read_sheet_rows(path, sheet_name)
    if not excel_headers:
        print(f"  [skip] 无列头: {keyword}/{sheet_name}")
        return 0

    catalog_headers = sorted(set(excel_headers))
    col_map = _upsert_catalog_columns(db, catalog_sheet, catalog_headers, fact_table)
    db.commit()

    header_to_db = {h: c.db_column for h, c in col_map.items()}
    clear_production_fact_rows(engine, fact_table, store_id)

    import_ts = int(time.time())
    key_headers = REQUIRED_COLUMNS.get((keyword, sheet_name), [])[:1]
    payload: list[dict] = []
    for rec in records:
        if not is_valid_data_row(rec, key_headers):
            continue
        payload.append(
            excel_record_to_production_row(
                rec,
                fact_table,
                header_to_db,
                store_id=store_id,
                excel_order_id=batch_id,
                shop_code=shop_code,
                import_time=import_ts,
            )
        )

    count = insert_fact_rows(engine, fact_table, payload)
    db.commit()
    return count


def main(setup_rules: bool = True) -> None:
    if engine.dialect.name == "sqlite":
        print("警告: 当前 DATABASE_URL 为 SQLite，生产请改为 MySQL。")

    run_migrations()
    db = SessionLocal()
    try:
        ensure_logical_fields(db)
        ds = ensure_meichong_datasource(db)
        ensure_production_fact_schema(db, ds.id)
        sync_store_production_ids(db)
        removed = cleanup_legacy_fact_catalog(db, ds.id)
        if removed:
            print(f"已清理 legacy Catalog Sheet: {removed} 个")

        if setup_rules:
            apply_meichong_rules(db, reset=False)

        _ensure_store(db, ds)

        batch = EtlBatch(
            data_source_id=ds.id,
            store_name=MEICHONG_STORE,
            source_desc="美宠 Excel ETL [production]",
            row_counts={},
            status="running",
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)
        batch.excel_order_id = batch.id
        db.commit()

        files_dir = Path(settings.files_dir)
        xlsx_files = sorted(p for p in files_dir.glob("*.xlsx") if "日报模板" not in p.name)

        totals: dict[str, int] = {}
        t_all = time.time()
        for path in xlsx_files:
            keyword = _match_keyword(path.name)
            sheets = _match_sheets(path.name)
            if not keyword or not sheets:
                print(f"[skip] 未识别: {path.name}")
                continue
            print(f"[etl] {path.name} keyword={keyword}", flush=True)
            for sheet_name in sorted(sheets):
                t0 = time.time()
                try:
                    n = _import_sheet(
                        db, ds.id, MEICHONG_STORE, batch.id, path, keyword, sheet_name
                    )
                    key = f"{keyword}/{sheet_name}"
                    totals[key] = n
                    print(f"  -> {key}: {n} rows ({time.time() - t0:.1f}s)", flush=True)
                except Exception as exc:
                    print(f"  !! {sheet_name} 失败: {exc!r}", flush=True)
                    batch.status = "partial"
                    db.commit()

        batch.row_counts = totals
        if batch.status == "running":
            batch.status = "success"
        db.commit()

        print(f"\n=== ETL 完成 batch #{batch.id}，耗时 {time.time() - t_all:.1f}s ===")
        for k, v in sorted(totals.items()):
            print(f"  {k}: {v}")
        print(f"  合计: {sum(totals.values())} 行")
    finally:
        db.close()


if __name__ == "__main__":
    skip_rules = "--skip-rules" in sys.argv
    main(setup_rules=not skip_rules)
