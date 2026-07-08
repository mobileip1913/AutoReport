"""生产事实表读写辅助：store_id 解析、extra_data 展开、Excel 值类型清洗。"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, time
from typing import Any

from sqlalchemy.orm import Session

from app.models import DataSource, Store
from app.services.field_aggregator import parse_date
from app.services.production_schema import column_sql_type, db_column_to_header

_NON_NUMERIC = frozenset({"/", "-", "—", "no", "yes", "n/a", "null", "none"})


def uses_production_schema(db: Session, data_source_id: int, fact_tables: list[str] | None = None) -> bool:
    """生产库为标准形态，始终按 eb_overseas_tk_* + store_id 读数。"""
    return True


def resolve_production_store(
    db: Session, data_source_id: int, store_name: str
) -> tuple[int | None, str | None]:
    """返回 (production_store_id, shop_code)。"""
    store = db.query(Store).filter(Store.data_source_id == data_source_id).first()
    if store and store.production_store_id:
        return store.production_store_id, store.shop_code

    ds = db.query(DataSource).filter(DataSource.id == data_source_id).first()
    cfg = (ds.config or {}) if ds else {}
    store_id = cfg.get("production_store_id")
    shop_code = cfg.get("shop_code")
    if store_id is not None:
        return int(store_id), shop_code
    return None, shop_code


def merge_extra_data(row: dict[str, Any], extra_raw: Any) -> dict[str, Any]:
    """将 extra_data JSON 合并进 row_data（header 为键）。"""
    if not extra_raw:
        return row
    if isinstance(extra_raw, str):
        try:
            extra = json.loads(extra_raw)
        except json.JSONDecodeError:
            return row
    elif isinstance(extra_raw, dict):
        extra = extra_raw
    else:
        return row
    for key, val in extra.items():
        if key not in row or row[key] is None:
            row[key] = val
    return row


def expand_production_record(
    record: dict[str, Any],
    table_name: str,
    header_by_db: dict[str, str],
) -> dict[str, Any]:
    """DB 行 → 聚合器使用的 header 键字典。"""
    row_data: dict[str, Any] = {}
    for db_col, header in header_by_db.items():
        val = record.get(db_col)
        if val is not None:
            row_data[header] = val
    extra = record.get("extra_data")
    if extra:
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except json.JSONDecodeError:
                extra = None
        if isinstance(extra, dict):
            for key, val in extra.items():
                header = db_column_to_header(table_name, key) or key
                if header not in row_data or row_data[header] is None:
                    row_data[header] = val
    return row_data


def _looks_like_instruction_text(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if len(text) < 20:
        return False
    lower = text.lower()
    if "unique " in lower and "id" in lower:
        return True
    if text.endswith(".") and " " in text and not text[0].isdigit() and len(text) > 25:
        return True
    return (
        text.startswith("The ")
        or " when the " in lower
        or (" when " in lower and len(text) > 60)
    )


def _is_plausible_key_value(header: str, val: Any) -> bool:
    text = str(val).strip() if val is not None else ""
    if not text:
        return False
    if _looks_like_instruction_text(text):
        return False
    h = header.lower()
    if "order id" in h or h == "order id":
        if " " in text and len(text) > 24:
            return False
        if "unique" in text.lower() or "platform" in text.lower():
            return False
    return True


def is_valid_data_row(rec: dict[str, Any], key_headers: list[str]) -> bool:
    """跳过 TikTok 导出中的说明行、空行。"""
    if not key_headers:
        return True
    for header in key_headers:
        if _is_plausible_key_value(header, rec.get(header)):
            return True
    return False


def _coerce_decimal(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    text = str(val).strip().replace(",", "").replace("$", "").replace("%", "")
    if not text or text.lower() in _NON_NUMERIC:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _coerce_int(val: Any) -> int | None:
    num = _coerce_decimal(val)
    if num is None:
        return None
    return int(num)


def _coerce_datetime(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(val, date):
        return datetime.combine(val, time.min).strftime("%Y-%m-%d %H:%M:%S")
    text = str(val).strip()
    if not text or text in {"/", "-"} or _looks_like_instruction_text(text):
        return None
    if re.match(r"^\d{4}[-/]\d", text):
        parsed = parse_date(text, "iso")
        if parsed:
            return datetime.combine(parsed, time.min).strftime("%Y-%m-%d %H:%M:%S")
    parsed = parse_date(text, None)
    if parsed:
        return datetime.combine(parsed, time.min).strftime("%Y-%m-%d %H:%M:%S")
    return None


def coerce_production_value(table_name: str, db_column: str, val: Any) -> Any | None:
    sql_type = column_sql_type(table_name, db_column)
    if not sql_type:
        return val
    if sql_type == "DATETIME":
        return _coerce_datetime(val)
    if sql_type in {"DECIMAL"}:
        return _coerce_decimal(val)
    if sql_type in {"INT", "BIGINT", "TINYINT"}:
        return _coerce_int(val)
    if sql_type == "VARCHAR":
        text = str(val).strip() if val is not None else ""
        return text or None
    return val


def excel_record_to_production_row(
    rec: dict[str, Any],
    table_name: str,
    header_to_db: dict[str, str],
    *,
    store_id: int,
    excel_order_id: int,
    shop_code: str | None,
    import_time: int,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "store_id": store_id,
        "excel_order_id": excel_order_id,
        "import_time": import_time,
        "shop_code": shop_code,
    }
    extra: dict[str, Any] = {}
    for header, val in rec.items():
        if val is None or str(val).strip() == "":
            continue
        db_col = header_to_db.get(header)
        if not db_col:
            extra[header] = val
            continue
        coerced = coerce_production_value(table_name, db_col, val)
        if coerced is None:
            raw = str(val).strip()
            if raw and raw not in {"/", "-"}:
                extra[header] = val
            continue
        row[db_col] = coerced
    if extra:
        row["extra_data"] = json.dumps(extra, ensure_ascii=False)
    return row
