"""逻辑字段取数：多 Sheet/多文件、加减组合、去重聚合，并支持日报规则增强：
行级日期过滤、行条件过滤、样品/刷单排除、与订单表关联。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

from app.models import DataRow, FieldMapping, FieldMappingPart
from app.services.ds_settings import DEFAULT_JOIN_KEYS

ORDER_ID_CANDIDATES = ["Order ID", "Related order ID", "Order/adjustment ID", "订单号"]
SKU_ID_CANDIDATES = ["SKU ID", "Sku Id", "Sku ID", "SKU Id"]
REFUND_DATE_COLUMNS = ["Refund Time", "退款时间"]


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
    # 当日有效订单（日期主表日期=报表日 且 非样品 非刷单），供跨表关联
    valid_order_keys: set[tuple[str, str]] = field(default_factory=set)
    valid_order_ids: set[str] = field(default_factory=set)
    # 当日下单且当日退款的 Order ID（报表日口径）
    same_day_refund_order_ids: set[str] = field(default_factory=set)
    # 关联键列头元组 → 有效值元组集合
    valid_join_map: dict[tuple[str, ...], set[tuple[str, ...]]] = field(default_factory=dict)
    valid_master_rows: list[dict] = field(default_factory=list)


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
    for row in cfg.get("sample_orders") or []:
        oid = str(row.get("order_id", "")).strip()
        if oid:
            sample_ids.add(oid)
    for oid in cfg.get("sample_order_ids") or []:
        oid = str(oid).strip()
        if oid:
            sample_ids.add(oid)
    review_ids = {str(x).strip() for x in (cfg.get("review_order_ids") or [])}

    valid_keys: set[tuple[str, str]] = set()
    valid_ids: set[str] = set()
    valid_row_norms: list[dict] = []
    for r in rows:
        if order_sheet and r.sheet_name != order_sheet:
            continue
        nd = _normalized(r.row_data)
        oid = str(nd.get(order_id_col, "")).strip()
        if not oid:
            continue
        sku = str(nd.get(sku_id_col, "")).strip()
        d = parse_date(nd.get(order_date_col), order_date_fmt) if order_date_col else None
        if oid in sample_ids or oid in review_ids:
            continue
        if report_d is not None and d != report_d:
            continue
        valid_keys.add((oid, sku))
        valid_ids.add(oid)
        valid_row_norms.append(nd)

    def _join_set(cols: list[str]) -> set[tuple[str, ...]]:
        kt = tuple(cols)
        out: set[tuple[str, ...]] = set()
        for nd in valid_row_norms:
            t = tuple(str(nd.get(c, "")).strip() for c in cols)
            if all(t):
                out.add(t)
        return out

    valid_join_map: dict[tuple[str, ...], set[tuple[str, ...]]] = {
        (order_id_col,): _join_set([order_id_col]),
        (order_id_col, sku_id_col): _join_set([order_id_col, sku_id_col]),
        tuple(DEFAULT_JOIN_KEYS): _join_set(list(DEFAULT_JOIN_KEYS)),
    }

    placed_today_ids: set[str] = set()
    refunded_today_ids: set[str] = set()
    if report_d is not None:
        refund_date_fmt = cfg.get("refund_date_format", "eu")
        for r in rows:
            nd = _normalized(r.row_data)
            oid = _extract(r.row_data, ORDER_ID_CANDIDATES)
            if not oid:
                continue
            if order_sheet and r.sheet_name == order_sheet and order_date_col:
                placed = parse_date(nd.get(order_date_col), order_date_fmt)
                if placed == report_d:
                    placed_today_ids.add(oid)
            for col in REFUND_DATE_COLUMNS:
                if col in nd:
                    refunded = parse_date(nd.get(col), refund_date_fmt)
                    if refunded == report_d:
                        refunded_today_ids.add(oid)
                    break

    same_day_refund_order_ids = placed_today_ids & refunded_today_ids

    return DailyContext(
        report_date=report_d,
        sample_order_ids=sample_ids,
        review_order_ids=review_ids,
        order_keys=order_keys,
        order_id_set=order_id_set,
        valid_order_keys=valid_keys,
        valid_order_ids=valid_ids,
        same_day_refund_order_ids=same_day_refund_order_ids,
        valid_join_map=valid_join_map,
        valid_master_rows=valid_row_norms,
    )


def _cell_str(raw) -> str:
    return "" if raw is None else str(raw).strip()


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
        cell = _cell_str(raw)
        vals = [str(v).strip() for v in values]
        lower_cell = cell.lower()
        lower_vals = [v.lower() for v in vals]

        if op == "nonempty":
            if not cell:
                return False
        elif op == "empty":
            if cell:
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
        elif op == "contains":
            needle = vals[0] if vals else ""
            if needle.lower() not in lower_cell:
                return False
        elif op == "not_contains":
            needle = vals[0] if vals else ""
            if needle.lower() in lower_cell:
                return False
        elif op == "starts_with":
            prefix = vals[0] if vals else ""
            if not lower_cell.startswith(prefix.lower()):
                return False
        elif op == "ends_with":
            suffix = vals[0] if vals else ""
            if not lower_cell.endswith(suffix.lower()):
                return False
        elif op == "between":
            num = _to_number(raw)
            lo = _to_number(vals[0]) if len(vals) > 0 else 0.0
            hi = _to_number(vals[1]) if len(vals) > 1 else lo
            if not (lo <= num <= hi):
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


def _match_join_keys(
    row_data: dict,
    join_keys: list[str],
    context: DailyContext,
) -> bool:
    keys = [k.strip() for k in (join_keys or []) if k and str(k).strip()]
    if not keys:
        keys = list(DEFAULT_JOIN_KEYS)
    key_tuple = tuple(keys)
    nd = _normalized(row_data)
    parts = tuple(str(nd.get(k, "")).strip() for k in keys)
    if not any(parts):
        return False
    valid_set = context.valid_join_map.get(key_tuple)
    if valid_set is None and context.valid_master_rows:
        valid_set = {
            t for t in (
                tuple(str(nd.get(k, "")).strip() for k in keys)
                for nd in context.valid_master_rows
            )
            if all(t)
        }
        context.valid_join_map[key_tuple] = valid_set
    if valid_set is None:
        if len(keys) == 2:
            return parts in context.valid_order_keys
        if len(keys) == 1:
            return parts[0] in context.valid_order_ids
        return False
    if all(parts):
        return parts in valid_set
    if len(keys) == 1:
        return parts[0] in context.valid_order_ids
    return False


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
    exclude_same_day_refund = bool(getattr(part, "exclude_same_day_refund", False))
    join_to_orders = bool(getattr(part, "join_to_orders", False))
    only_sample = bool(getattr(part, "only_sample", False))

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

        if context is not None and (exclude_sample or exclude_review or exclude_same_day_refund or join_to_orders or only_sample):
            oid = _extract(row.row_data, ORDER_ID_CANDIDATES)
            if only_sample and oid not in context.sample_order_ids:
                continue
            if exclude_sample and oid in context.sample_order_ids:
                continue
            if exclude_review and oid in context.review_order_ids:
                continue
            if exclude_same_day_refund and oid in context.same_day_refund_order_ids:
                continue
            if join_to_orders:
                join_keys = getattr(part, "join_keys", None) or []
                if not _match_join_keys(row.row_data, join_keys, context):
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
        row_filters=(
            src.get("row_filters")
            if src.get("row_filters") is not None
            else (base.row_filters or [])
        ),
        exclude_sample=base.exclude_sample,
        exclude_review=base.exclude_review,
        exclude_same_day_refund=getattr(base, "exclude_same_day_refund", False),
        join_to_orders=base.join_to_orders,
        join_keys=base.join_keys or [],
        only_sample=getattr(base, "only_sample", False),
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
    *,
    db=None,
    data_source_id: int | None = None,
) -> float:
    benchmark_keys = [k for k in (getattr(part, "benchmark_keys", None) or []) if k and str(k).strip()]
    if part.ref_field_code:
        if benchmark_keys and db is not None and data_source_id:
            return aggregate_line_code_with_benchmark(
                db, data_source_id, part.ref_field_code, rows, import_file_names, context, benchmark_keys
            )
        return float(field_values.get(part.ref_field_code, 0.0))
    effective = _join_override_part(part, benchmark_keys) if benchmark_keys else part
    return aggregate_part(rows, effective, import_file_names, context)


class _JoinOverridePart:
    """组间基准字段：强制按 benchmark_keys 关联日期主表有效行。"""

    def __init__(self, part: FieldMappingPart, benchmark_keys: list[str]):
        self._part = part
        self._benchmark_keys = benchmark_keys

    def __getattr__(self, name: str):
        if name == "join_keys" and self._benchmark_keys:
            return self._benchmark_keys
        if name == "join_to_orders" and self._benchmark_keys:
            return True
        return getattr(self._part, name)


def _join_override_part(part: FieldMappingPart, benchmark_keys: list[str]) -> _JoinOverridePart:
    return _JoinOverridePart(part, benchmark_keys)


def aggregate_mapping_with_benchmark(
    mapping: FieldMapping,
    rows: list,
    import_file_names: dict[int, str],
    context: DailyContext | None,
    benchmark_keys: list[str],
) -> float:
    parts = sorted(mapping.parts, key=lambda p: p.sort_order)
    values = [
        aggregate_part(rows, _join_override_part(p, benchmark_keys), import_file_names, context)
        for p in parts
    ]
    return combine_parts(parts, values)


def aggregate_line_code_with_benchmark(
    db,
    data_source_id: int,
    line_code: str,
    rows: list,
    import_file_names: dict[int, str],
    context: DailyContext | None,
    benchmark_keys: list[str],
) -> float:
    from app.models import FieldMapping

    mapping = (
        db.query(FieldMapping)
        .filter(FieldMapping.data_source_id == data_source_id, FieldMapping.line_code == line_code)
        .first()
    )
    if not mapping or not mapping.parts:
        return 0.0
    return aggregate_mapping_with_benchmark(mapping, rows, import_file_names, context, benchmark_keys)


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
