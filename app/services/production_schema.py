"""生产库 `eb_overseas_tk_*` 表结构：从 DDL 解析列名与 Excel 表头（COMMENT）映射。"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DDL = ROOT / "sql" / "跨境订单建表语句_v2.sql"

# Catalog 文件关键字 + Sheet → 生产事实表（与 sql/数据库对比说明.md 一致）
PRODUCTION_TABLE_BY_SHEET: dict[tuple[str, str], str] = {
    ("订单", "OrderSKUList"): "eb_overseas_tk_order",
    ("退货退款单", "0"): "eb_overseas_tk_order_return",
    ("联盟达人佣金", "Sheet1"): "eb_overseas_tk_affiliate_creator",
    ("联盟服务商佣金", "Sheet1"): "eb_overseas_tk_affiliate_partner",
    ("结算表", "Order details"): "eb_overseas_tk_finance_statements",
    ("未结算单", "Unsettled order and adjustment"): "eb_overseas_tk_finance_on_hold",
}

PRODUCTION_PUBLIC_COLUMNS = frozenset({
    "id", "store_id", "excel_order_id", "import_time", "shop_code", "extra_data",
})

_COLUMN_LINE_RE = re.compile(
    r"^\s*`(?P<col>[a-z0-9_]+)`\s+.+?(?:COMMENT\s+'(?P<comment>[^']*)')?\s*,?\s*$",
    re.IGNORECASE,
)
_TABLE_RE = re.compile(
    r"CREATE TABLE `(?P<table>eb_overseas_tk_[a-z_]+)`\s*\(",
    re.IGNORECASE,
)


_COLUMN_TYPE_RE = re.compile(
    r"^\s*`(?P<col>[a-z0-9_]+)`\s+(?P<type>DECIMAL|DATETIME|INT|BIGINT|TINYINT|VARCHAR|JSON)\b",
    re.IGNORECASE,
)


def _parse_table_body(body: str) -> tuple[dict[str, str], dict[str, str]]:
    cols: dict[str, str] = {}
    types: dict[str, str] = {}
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("`"):
            continue
        m = _COLUMN_LINE_RE.match(line)
        if not m:
            continue
        col = m.group("col")
        if col in PRODUCTION_PUBLIC_COLUMNS:
            continue
        comment = (m.group("comment") or "").strip()
        if comment:
            cols[col] = comment
        tm = _COLUMN_TYPE_RE.match(line)
        if tm:
            types[col] = tm.group("type").upper()
    return cols, types


@lru_cache(maxsize=1)
def load_production_schema(ddl_path: str | None = None) -> dict[str, dict[str, str]]:
    """返回 {table_name: {db_column: excel_header_comment}}，不含公共扩展列。"""
    path = Path(ddl_path) if ddl_path else DEFAULT_DDL
    text = path.read_text(encoding="utf-8")
    tables: dict[str, dict[str, str]] = {}
    for match in _TABLE_RE.finditer(text):
        table = match.group("table")
        start = match.end()
        depth = 1
        end = start
        while end < len(text) and depth > 0:
            if text[end] == "(":
                depth += 1
            elif text[end] == ")":
                depth -= 1
            end += 1
        body = text[start : end - 1]
        cols, _ = _parse_table_body(body)
        tables[table] = cols
    return tables


@lru_cache(maxsize=1)
def load_production_column_types(ddl_path: str | None = None) -> dict[str, dict[str, str]]:
    """返回 {table_name: {db_column: SQL_TYPE}}。"""
    path = Path(ddl_path) if ddl_path else DEFAULT_DDL
    text = path.read_text(encoding="utf-8")
    tables: dict[str, dict[str, str]] = {}
    for match in _TABLE_RE.finditer(text):
        table = match.group("table")
        start = match.end()
        depth = 1
        end = start
        while end < len(text) and depth > 0:
            if text[end] == "(":
                depth += 1
            elif text[end] == ")":
                depth -= 1
            end += 1
        body = text[start : end - 1]
        _, types = _parse_table_body(body)
        tables[table] = types
    return tables


def column_sql_type(table_name: str, db_column: str) -> str | None:
    return (load_production_column_types().get(table_name) or {}).get(db_column)


def header_to_db_column(table_name: str, header: str) -> str | None:
    """Excel 表头 → 生产 db_column；未知列返回 None（应写入 extra_data）。"""
    schema = load_production_schema()
    cols = schema.get(table_name) or {}
    header = (header or "").strip()
    if not header:
        return None
    for db_col, comment in cols.items():
        if comment == header:
            return db_col
    return None


def db_column_to_header(table_name: str, db_column: str) -> str | None:
    schema = load_production_schema()
    return (schema.get(table_name) or {}).get(db_column)


def production_tables() -> list[str]:
    return list(load_production_schema().keys())


def is_production_fact_table(table_name: str) -> bool:
    return table_name.startswith("eb_overseas_tk_")
