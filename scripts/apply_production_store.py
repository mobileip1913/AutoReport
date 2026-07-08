# -*- coding: utf-8 -*-
"""导入生产店铺主表 sql/eb_overseas_store.sql，并同步美宠店 store_id 到 AutoReport。

用法：
    python scripts/apply_production_store.py
    python scripts/apply_production_store.py --no-drop
    python scripts/apply_production_store.py --sync-only
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.database import SessionLocal, engine
from app.services.migrate import run_migrations
from app.services.production_store import lookup_production_store, sync_store_production_ids

SQL_PATH = ROOT / "sql" / "eb_overseas_store.sql"


def _split_statements(sql_text: str, *, include_drop: bool) -> list[str]:
    text_clean = re.sub(r"/\*.*?\*/", "", sql_text, flags=re.DOTALL)
    statements: list[str] = []
    for part in text_clean.split(";"):
        stmt = part.strip()
        if not stmt or stmt.startswith("--"):
            continue
        upper = stmt.upper()
        if not include_drop and upper.startswith("DROP TABLE"):
            continue
        statements.append(stmt)
    return statements


def apply_store_sql(include_drop: bool = True) -> None:
    if engine.dialect.name != "mysql":
        print("警告: 店铺主表 SQL 面向 MySQL，当前方言:", engine.dialect.name)

    run_migrations()
    sql_text = SQL_PATH.read_text(encoding="utf-8")
    statements = _split_statements(sql_text, include_drop=include_drop)
    print(f"执行 {len(statements)} 条 SQL …")
    with engine.begin() as conn:
        for i, stmt in enumerate(statements, 1):
            preview = stmt.split("\n", 1)[0][:80]
            print(f"  [{i}/{len(statements)}] {preview}")
            conn.execute(text(stmt))
    print("eb_overseas_store 已导入。")


def sync_meichong_store() -> None:
    db = SessionLocal()
    try:
        result = sync_store_production_ids(db)
        if not result:
            raise SystemExit("未找到美宠店铺记录，请先导入 sql/eb_overseas_store.sql")
        print(
            f"已同步：{result['store_name']} → "
            f"production_store_id={result['production_store_id']}, shop_code={result['shop_code']!r}"
        )
    finally:
        db.close()


def verify() -> bool:
    prod = lookup_production_store("平衡贴美国本土店铺")
    if not prod:
        print("[FAIL] eb_overseas_store 中未找到「平衡贴美国本土店铺」")
        return False
    if int(prod["id"]) != 3:
        print(f"[WARN] store_id 非预期 3，实际为 {prod['id']}")
    if prod.get("shop_code") != "USLCQPEV3N":
        print(f"[WARN] shop_code 非预期，实际为 {prod.get('shop_code')!r}")

    db = SessionLocal()
    try:
        from app.models import DataSource, Store
        from app.services.production_fact import resolve_production_store
        from app.services.seed import MEICHONG_SOURCE_NAME

        ds = db.query(DataSource).filter(DataSource.name == MEICHONG_SOURCE_NAME).first()
        store = db.query(Store).filter(Store.data_source_id == ds.id).first() if ds else None
        if not store or store.production_store_id != int(prod["id"]):
            print(f"[FAIL] stores.production_store_id 未对齐，当前={getattr(store, 'production_store_id', None)}")
            return False
        sid, code = resolve_production_store(db, ds.id, store.name)
        if sid != int(prod["id"]) or code != prod.get("shop_code"):
            print(f"[FAIL] resolve_production_store 返回 ({sid}, {code!r})")
            return False
        cfg = ds.config or {}
        if cfg.get("production_store_id") != int(prod["id"]):
            print(f"[FAIL] data_sources.config.production_store_id={cfg.get('production_store_id')}")
            return False
        print(
            f"[OK] 生产店 id={prod['id']}, shop_code={prod.get('shop_code')!r}；"
            f"AutoReport stores/config 已对齐"
        )
        return True
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="导入生产店铺主表并同步美宠 store_id")
    parser.add_argument("--no-drop", action="store_true", help="跳过 DROP TABLE")
    parser.add_argument("--sync-only", action="store_true", help="仅同步 AutoReport stores/config，不执行 SQL")
    parser.add_argument("--verify", action="store_true", help="导入后校验")
    args = parser.parse_args()

    if not args.sync_only:
        apply_store_sql(include_drop=not args.no_drop)
    sync_meichong_store()
    if args.verify or not args.sync_only:
        ok = verify()
        if not ok:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
