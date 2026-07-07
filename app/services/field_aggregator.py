"""逻辑字段取数：多 Sheet/多文件、加减组合、去重聚合，并支持日报规则增强：
行级日期过滤、行条件过滤、样品/刷单排除、与订单表关联。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

from app.models import DataRow, FieldMappingPart

ORDER_ID_CANDIDATES = ["Order ID", "Related order ID", "Order/adjustment ID", "订单号"]
SKU_ID_CANDIDATES = ["SKU ID", "Sku Id", "Sku ID", "SKU Id"]


def _to_number(value) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text in {"/", "-"}:
        return 0.0
    neg = text.startswith("(") and text.endswith(")")
    text = text.strip("()").replace(",", "").replace("$", "").replace("%", "").replace("\u00a5", "").strip()
    try:
        num = float(text)
        return -num if neg else num
    except (TypeError, ValueError):
        return 0.0


def _normalized(row_data: dict) -> dict:
    return {str(k).strip(): v for k, v in row_data.items()}


def _cell(row_data: dict, column_header: str, aliases: list) -> float | None:
    candidates = [column_header, *aliases]
    normalized = _normalized(row_data)
    for name in candidates:
        key = str(name).strip()
        if key in normalized:
            return _to_number(normalized[key])
    return None


def _extract(row_data: dict, candidates: list[str]) -> str:
    normalized = _normalized(row_data)
    for name in candidates:
        if name in normalized:
            v = normalized[name]
            if v is not None and str(v).strip():
                return str(v).strip()
    return ""


def parse_date(value, fmt: str | None = None) -> date | None:
    """解析多格式日期为 date：us=MM/DD/YYYY, eu=DD/MM/YYYY, iso=YYYY/MM/DD，None=自动。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text or text in {"/", "-"}:
        return None
    token = text.split(" ")[0].split("T")[0]
    sep = "/" if "/" in token else ("-" if "-" in token else None)
    if sep is None:
        return None
    parts = token.split(sep)
    if len(parts) != 3:
        return None
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None

    a, b, c = nums
    try:
        if fmt == "iso" or len(parts[0]) == 4 or a > 31:
            y, m, d = a, b, c
        elif fmt == "eu":
            d, m, y = a, b, c
        elif fmt == "us":
            m, d, y = a, b, c
        else:  # 自动判别
            if a > 12:
                d, m, y = a, b, c
            elif b > 12:
                m, d, y = a, b, c
            else:
                m, d, y = a, b, c  # 默认按美国格式（TK-US 店铺）
        return date(y, m, d)
    except ValueError:
        return None


@dataclass
class DailyContext:
    report_date: date | None
    sample_order_ids: set[str] = field(default_factory=set)
    review_order_ids: set[str] = field(default_factory=set)
    order_keys: set[tuple[str, str]] = field(default_factory=set)
    order_id_set: set[str] = field(default_factory=set)
    # 当日有效订单（Created Time=报表日 且 非样品 非刷单），供达人/服务商佣金关联
    valid_order_keys: set[tuple[str, str]] = field(default_factory=set)
    valid_order_ids: set[str] = field(default_factory=set)


def build_daily_context(rows: list[DataRow], ds_config: dict, report_date: str) -> DailyContext:
    cfg = ds_config or {}
    order_sheet = cfg.get("order_sheet")
    order_id_col = cfg.get("order_id_col", "Order ID")
    sku_id_col = cfg.get("sku_id_col", "SKU ID")
    order_date_col = cfg.get("order_date_col")
    order_date_fmt = cfg.get("order_date_format")
    sample_rule = cfg.get("sample_rule") or {}
    sum_cols = sample_rule.get("sum_cols", [])

    report_d = parse_date(report_date, "iso")

    per_order: dict[str, float] = defaultdict(float)
    order_keys: set[tuple[str, str]] = set()
    order_id_set: set[str] = set()
    order_date_map: dict[tuple[str, str], date | None] = {}

    for r in rows:
        if order_sheet and r.sheet_name != order_sheet:
            continue
        nd = _normalized(r.row_data)
        oid = str(nd.get(order_id_col, "")).strip()
        if not oid:
            continue
        order_id_set.add(oid)
        sku = str(nd.get(sku_id_col, "")).strip()
        order_keys.add((oid, sku))
        if order_date_col:
            order_date_map[(oid, sku)] = parse_date(nd.get(order_date_col), order_date_fmt)
        if sum_cols:
            per_order[oid] += sum(_to_number(nd.get(c)) for c in sum_cols)

    sample_ids = {oid for oid, total in per_order.items() if abs(total) < 0.01}
    review_ids = {str(x).strip() for x in (cfg.get("review_order_ids") or [])}

    valid_keys: set[tuple[str, str]] = set()
    valid_ids: set[str] = set()
    for (oid, sku), d in order_date_map.items():
        if oid in sample_ids or oid in review_ids:
            continue
        if report_d is not None and d != report_d:
            continue
        valid_keys.add((oid, sku))
        valid_ids.add(oid)

    return DailyContext(
        report_date=report_d,
        sample_order_ids=sample_ids,
        review_order_ids=review_ids,
        order_keys=order_keys,
        order_id_set=order_id_set,
        valid_order_keys=valid_keys,
        valid_order_ids=valid_ids,
    )


def _passes_row_filters(row_data: dict, filters: list[dict]) -> bool:
    if not filters:
        return True
    normalized = _normalized(row_data)
    for cond in filters:
        col = str(cond.get("column", "")).strip()
        op = cond.get("op", "eq")
        values = cond.get("values", [])
        if isinstance(values, (str, int, float)):
            values = [values]
        raw = normalized.get(col)
        cell = "" if raw is None else str(raw).strip()
        vals = [str(v).strip() for v in values]

        if op == "nonempty":
            if not cell:
                return False
        elif op == "eq":
            if cell != (vals[0] if vals else ""):
                return False
        elif op == "ne":
            if cell == (vals[0] if vals else ""):
                return False
        elif op == "in":
            if cell not in vals:
                return False
        elif op == "not_in":
            if cell in vals:
                return False
        elif op in ("gt", "gte", "lt", "lte"):
            num = _to_number(raw)
            target = _to_number(vals[0]) if vals else 0.0
            if op == "gt" and not num > target:
                return False
            if op == "gte" and not num >= target:
                return False
            if op == "lt" and not num < target:
                return False
            if op == "lte" and not num <= target:
                return False
    return True


def _filter_rows(
    rows: list[DataRow],
    part: FieldMappingPart,
    import_file_names: dict[int, str],
    context: DailyContext | None,
) -> list[DataRow]:
    result = []
    keyword = (part.source_file_keyword or "").strip().lower()
    date_col = (getattr(part, "date_filter_column", None) or "").strip()
    date_fmt = getattr(part, "date_format", None)
    row_filters = getattr(part, "row_filters", None) or []
    exclude_sample = bool(getattr(part, "exclude_sample", False))
    exclude_review = bool(getattr(part, "exclude_review", False))
    join_to_orders = bool(getattr(part, "join_to_orders", False))

    for row in rows:
        if row.sheet_name != part.sheet_name:
            continue
        if keyword:
            file_name = import_file_names.get(row.data_import_id, "").lower()
            if keyword not in file_name:
                continue

        nd = _normalized(row.row_data)

        if date_col and context is not None and context.report_date is not None:
            d = parse_date(nd.get(date_col), date_fmt)
            if d != context.report_date:
                continue

        if context is not None and (exclude_sample or exclude_review or join_to_orders):
            oid = _extract(row.row_data, ORDER_ID_CANDIDATES)
            if exclude_sample and oid in context.sample_order_ids:
                continue
            if exclude_review and oid in context.review_order_ids:
                continue
            if join_to_orders:
                sku = _extract(row.row_data, SKU_ID_CANDIDATES)
                if (oid, sku) not in context.valid_order_keys and oid not in context.valid_order_ids:
                    continue

        if not _passes_row_filters(row.row_data, row_filters):
            continue

        result.append(row)
    return result


def _dedup_key(row_data: dict, dedup_keys: list[str]) -> tuple:
    if not dedup_keys:
        return (id(row_data),)
    parts = []
    normalized = _normalized(row_data)
    for key in dedup_keys:
        parts.append(str(normalized.get(key.strip(), "")))
    return tuple(parts)


def _source_part(base: FieldMappingPart, src: dict) -> FieldMappingPart:
    """组内单列：继承块级规则，覆盖文件/Sheet/列头。"""
    p = FieldMappingPart(
        source_file_keyword=(src.get("source_file_keyword") or base.source_file_keyword or "").strip() or None,
        sheet_name=(src.get("sheet_name") or base.sheet_name or "").strip(),
        column_header=(src.get("column_header") or base.column_header or "").strip(),
        aliases=base.aliases or [],
        aggregation=base.aggregation,
        dedup_keys=base.dedup_keys or [],
        date_filter_column=base.date_filter_column,
        date_format=base.date_format,
        row_filters=base.row_filters or [],
        exclude_sample=base.exclude_sample,
        exclude_review=base.exclude_review,
        join_to_orders=base.join_to_orders,
    )
    return p


def _aggregate_single_source(
    rows: list[DataRow],
    part: FieldMappingPart,
    import_file_names: dict[int, str],
    context: DailyContext | None = None,
) -> float:
    matched = _filter_rows(rows, part, import_file_names, context)
    if not matched:
        return 0.0

    agg = part.aggregation or "sum"
    dedup_keys = part.dedup_keys or []

    if agg == "count":
        return float(len(matched))

    if agg == "count_distinct":
        keys = {_dedup_key(r.row_data, dedup_keys) for r in matched}
        return float(len(keys))

    if agg == "sum_dedup":
        groups: dict[tuple, float] = {}
        for row in matched:
            val = _cell(row.row_data, part.column_header, part.aliases or [])
            if val is None:
                continue
            key = _dedup_key(row.row_data, dedup_keys)
            groups[key] = val
        return sum(groups.values())

    if agg == "max_dedup":
        groups = {}
        for row in matched:
            val = _cell(row.row_data, part.column_header, part.aliases or [])
            if val is None:
                continue
            key = _dedup_key(row.row_data, dedup_keys)
            groups[key] = max(groups.get(key, val), val)
        return sum(groups.values())

    values: list[float] = []
    for row in matched:
        val = _cell(row.row_data, part.column_header, part.aliases or [])
        if val is not None:
            values.append(val)

    if not values:
        return 0.0
    if agg == "avg":
        return sum(values) / len(values)
    return sum(values)


def aggregate_part(
    rows: list[DataRow],
    part: FieldMappingPart,
    import_file_names: dict[int, str],
    context: DailyContext | None = None,
) -> float:
    """单条规则块：组内多列先各自聚合，再按 combine_op 组合。"""
    sources = getattr(part, "sources", None) or []
    if not sources:
        sources = [{
            "source_file_keyword": part.source_file_keyword,
            "sheet_name": part.sheet_name,
            "column_header": part.column_header,
            "combine_op": "add",
        }]
    total = 0.0
    started = False
    for src in sources:
        sub = _source_part(part, src)
        val = _aggregate_single_source(rows, sub, import_file_names, context)
        op = src.get("combine_op") or "add"
        if not started:
            total = -val if op == "subtract" else val
            started = True
            continue
        if op == "subtract":
            total -= val
        else:
            total += val
    return total if started else 0.0


def resolve_part_value(
    part: FieldMappingPart,
    rows: list,
    import_file_names: dict[int, str],
    context,
    field_values: dict[str, float],
) -> float:
    if part.ref_field_code:
        return float(field_values.get(part.ref_field_code, 0.0))
    return aggregate_part(rows, part, import_file_names, context)


def combine_parts(parts: list[FieldMappingPart], part_values: list[float]) -> float:
    total = 0.0
    started = False
    for part, value in zip(parts, part_values):
        op = part.combine_op or "add"
        if not started:
            total = value if op != "subtract" else -value
            started = True
            continue
        if op == "subtract":
            total -= value
        else:
            total += value
    return total if started else 0.0


AGGREGATION_LABELS = {
    "sum": "求和 sum — 所有行相加（SKU 级折扣）",
    "count": "计数 count — 行数",
    "count_distinct": "去重计数 — 按去重键统计唯一值（订单数）",
    "sum_dedup": "去重求和 — 每组只取一次再相加（订单级金额/折扣）",
    "max_dedup": "去重取最大 — 每组取最大再相加",
    "avg": "平均值 avg",
}
