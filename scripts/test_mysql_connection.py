# -*- coding: utf-8 -*-
"""测试 MySQL 连接。用法: python scripts/test_mysql_connection.py"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.config import settings
from app.database import engine


def main() -> None:
    url = settings.database_url
    safe = url.split("@")[-1] if "@" in url else url
    print(f"DATABASE_URL -> ...@{safe}")
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT VERSION()")).scalar()
            print(f"连接成功，MySQL 版本: {version}")
    except Exception as exc:
        print(f"连接失败: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
