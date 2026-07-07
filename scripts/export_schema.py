# -*- coding: utf-8 -*-
"""将数据源列结构导出为 data/schemas/ds_{id}.json（按需逐文件拉取，非全表扫描）。

用法：
    python scripts/export_schema.py
    python scripts/export_schema.py --data-source-id 4
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.database import SessionLocal
from app.models import DataSource
from app.services.schema import build_full_schema_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="导出字段映射 schema JSON")
    parser.add_argument("--data-source-id", type=int, default=None)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.data_source_id:
            sources = [db.query(DataSource).filter(DataSource.id == args.data_source_id).first()]
        else:
            sources = db.query(DataSource).all()
        out_dir = Path(settings.schemas_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for ds in sources:
            if not ds:
                continue
            snapshot = build_full_schema_snapshot(db, ds)
            if not snapshot.get("files"):
                print(f"skip ds_{ds.id} ({ds.name}): 无文件定义")
                continue
            path = out_dir / f"ds_{ds.id}.json"
            path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"wrote {path} ({len(snapshot['files'])} files)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
