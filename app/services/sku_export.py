"""按报表日期导出 SKU 销量明细 Excel。"""

from __future__ import annotations

import tempfile
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.models import DataSource, ReportRun
from app.services.ds_settings import get_ds_config
from app.services.fact_provider import load_fact_rows
from app.services.field_aggregator import (
    _extract,
    _normalized,
    _to_number,
    build_daily_context,
)

CANCELLED_STATUSES = frozenset({"Canceled", "Cancelled"})

EXPORT_COLUMNS = [
    ("order_id", "Order ID"),
    ("sku_id", "SKU ID"),
    ("seller_sku", "Seller SKU"),
    ("product_name", "Product Name"),
    ("quantity", "Quantity"),
    ("sku_subtotal", "SKU Subtotal After Discount"),
    ("sku_discount", "SKU Platform Discount"),
    ("order_amount", "Order Amount"),
]

QTY_CANDIDATES = ["Quantity", "SKU Quantity", "Item Quantity"]
SELLER_SKU_CANDIDATES = ["Seller SKU", "Seller Sku", "SKU"]
PRODUCT_CANDIDATES = ["Product Name", "Product", "Item Name"]


def _pick(nd: dict, candidates: list[str]) -> str:
    return _extract(nd, candidates)


def _pick_num(nd: dict, candidates: list[str]) -> float:
    for c in candidates:
        if c in nd:
            return _to_number(nd[c])
    return 0.0


def _sku_paid_amount(nd: dict) -> float:
    subtotal = _pick_num(nd, ["SKU Subtotal After Discount"])
    discount = _pick_num(nd, ["SKU Platform Discount"])
    return subtotal + discount


def collect_sku_rows(
    db: Session,
    ds: DataSource,
    report_date: str,
    store_name: str | None = None,
) -> list[dict]:
    cfg = get_ds_config(ds)
    store = store_name or (cfg.get("meta") or {}).get("店铺名称") or ds.name
    order_sheet = cfg.get("order_sheet") or "OrderSKUList"
    order_id_col = cfg.get("order_id_col") or "Order ID"
    sku_id_col = cfg.get("sku_id_col") or "SKU ID"

    rows, _ = load_fact_rows(db, ds.id, store)
    context = build_daily_context(rows, cfg, report_date)
    out: list[dict] = []
    for r in rows:
        if r.sheet_name != order_sheet:
            continue
        nd = _normalized(r.row_data)
        oid = _pick(nd, [order_id_col, "Order ID"])
        sku = _pick(nd, [sku_id_col, "SKU ID"])
        if not oid or not sku:
            continue
        if (oid, sku) not in context.valid_order_keys:
            continue
        status = _pick(nd, ["Order Status"])
        if status in CANCELLED_STATUSES:
            continue
        paid = _sku_paid_amount(nd)
        if paid <= 0.01:
            continue
        qty = _pick_num(nd, QTY_CANDIDATES)
        if qty <= 0:
            qty = 1.0
        out.append({
            "order_id": oid,
            "sku_id": sku,
            "seller_sku": _pick(nd, SELLER_SKU_CANDIDATES),
            "product_name": _pick(nd, PRODUCT_CANDIDATES),
            "quantity": qty,
            "sku_subtotal": _pick_num(nd, ["SKU Subtotal After Discount"]),
            "sku_discount": _pick_num(nd, ["SKU Platform Discount"]),
            "order_amount": _pick_num(nd, ["Order Amount"]),
        })
    return out


def export_sku_excel(
    db: Session,
    ds: DataSource,
    report_date: str,
    store_name: str | None = None,
) -> Path:
    data = collect_sku_rows(db, ds, report_date, store_name)
    wb = Workbook()
    ws = wb.active
    ws.title = "SKU销量"
    ws.append([label for _, label in EXPORT_COLUMNS])
    for row in data:
        ws.append([row[key] for key, _ in EXPORT_COLUMNS])

    store = store_name or (get_ds_config(ds).get("meta") or {}).get("店铺名称") or ds.name
    safe_store = "".join(c if c.isalnum() or c in "-_" else "_" for c in store)[:30]
    fname = f"SKU销量_{safe_store}_{report_date}.xlsx"
    path = Path(tempfile.gettempdir()) / fname
    wb.save(path)
    return path


def export_sku_for_run(db: Session, run: ReportRun, ds: DataSource) -> Path:
    return export_sku_excel(db, ds, run.report_date, run.store_name)
