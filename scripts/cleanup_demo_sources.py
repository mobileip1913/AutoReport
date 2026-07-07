# -*- coding: utf-8 -*-
"""删除老的 Demo 数据源（Amazon / Shopee / TikTok Shop UK）及其关联数据，仅保留美宠真实数据源。

用法（venv 下）：python scripts/cleanup_demo_sources.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models import (
    DataImport,
    DataRow,
    DataSource,
    FieldMapping,
    FieldMappingPart,
    MappingLog,
)
from app.services.seed import MEICHONG_SOURCE_NAME

# 要删除的 Demo 数据源名称
DEMO_SOURCE_NAMES = ["Amazon US 店铺", "Shopee SG 店铺", "TikTok Shop UK 店铺"]


def main() -> None:
    db = SessionLocal()
    try:
        sources = db.query(DataSource).filter(DataSource.name.in_(DEMO_SOURCE_NAMES)).all()
        if not sources:
            print("没有可删除的 Demo 数据源")
            return

        for ds in sources:
            mappings = db.query(FieldMapping).filter(FieldMapping.data_source_id == ds.id).all()
            for m in mappings:
                db.query(FieldMappingPart).filter(FieldMappingPart.mapping_id == m.id).delete()
            mapping_ids = [m.id for m in mappings]

            imports = db.query(DataImport).filter(DataImport.data_source_id == ds.id).all()
            import_ids = [i.id for i in imports]
            if import_ids:
                db.query(DataRow).filter(DataRow.data_import_id.in_(import_ids)).delete(synchronize_session=False)
                db.query(MappingLog).filter(MappingLog.data_import_id.in_(import_ids)).delete(synchronize_session=False)
            for i in imports:
                db.delete(i)
            for m in mappings:
                db.delete(m)
            db.delete(ds)
            print(f"已删除数据源 #{ds.id} {ds.name}（映射 {len(mapping_ids)}、导入 {len(import_ids)}）")

        db.commit()

        print("\n=== 剩余数据源 ===")
        for ds in db.query(DataSource).order_by(DataSource.id).all():
            tag = " (美宠)" if ds.name == MEICHONG_SOURCE_NAME else ""
            print(f"  #{ds.id}  {ds.name}{tag}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
