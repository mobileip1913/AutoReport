from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.services.meichong_rules import (
    MEICHONG_SOURCE_NAME,
    TEMPLATE_GROUPS,
    TEMPLATE_LINES,
    apply_meichong_rules,
)
from app.services.migrate import run_migrations
from app.services.report_line_sync import backfill_mapping_line_codes, sync_report_lines
from app.models import DataSource


def main() -> None:
    run_migrations()
    db = SessionLocal()
    try:
        n = backfill_mapping_line_codes(db)
        print(f"backfill line_code: {n} rows")

        ds = db.query(DataSource).filter(DataSource.name == MEICHONG_SOURCE_NAME).first()
        if not ds:
            print("美宠数据源不存在，先写入取数规则…")
            apply_meichong_rules(db, reset=False)
            ds = db.query(DataSource).filter(DataSource.name == MEICHONG_SOURCE_NAME).first()

        touched = sync_report_lines(
            db,
            ds.id,
            TEMPLATE_LINES,
            TEMPLATE_GROUPS,
            only_missing=False,
        )
        print(f"sync report lines for data_source_id={ds.id}: {touched} touched")

        total = db.query(__import__("app.models", fromlist=["FieldMapping"]).FieldMapping).filter_by(
            data_source_id=ds.id
        ).count()
        print(f"field_mappings count: {total}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
