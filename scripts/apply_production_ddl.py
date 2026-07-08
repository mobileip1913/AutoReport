# -*- coding: utf-8 -*-
"""在 MySQL 中执行生产库 DDL（sql/跨境订单建表语句_v2.sql）。

用法（项目根目录、已配置 .env DATABASE_URL）：
    python scripts/apply_production_ddl.py
    python scripts/apply_production_ddl.py --no-drop
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.database import engine
from app.services.migrate import run_migrations

DDL_PATH = ROOT / "sql" / "跨境订单建表语句_v2.sql"


def _split_statements(sql_text: str, *, include_drop: bool) -> list[str]:
    # 去掉块注释
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


def apply_ddl(include_drop: bool = True) -> None:
    if engine.dialect.name != "mysql":
        print("警告: 生产 DDL 面向 MySQL，当前方言:", engine.dialect.name)

    run_migrations()
    sql_text = DDL_PATH.read_text(encoding="utf-8")
    statements = _split_statements(sql_text, include_drop=include_drop)
    print(f"执行 {len(statements)} 条 DDL …")
    with engine.begin() as conn:
        for i, stmt in enumerate(statements, 1):
            preview = stmt.split("\n", 1)[0][:80]
            print(f"  [{i}/{len(statements)}] {preview}")
            conn.execute(text(stmt))
    print("生产表 DDL 已应用。")


def main() -> None:
    parser = argparse.ArgumentParser(description="应用生产库 eb_overseas_tk_* DDL")
    parser.add_argument("--no-drop", action="store_true", help="跳过 DROP TABLE（保留已有数据）")
    args = parser.parse_args()
    apply_ddl(include_drop=not args.no_drop)


if __name__ == "__main__":
    main()
