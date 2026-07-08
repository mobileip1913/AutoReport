"""数据源级配置：日期主表、定时出报等。"""

from __future__ import annotations

from copy import deepcopy

from sqlalchemy.orm import Session

from app.models import DataSource

DEFAULT_JOIN_KEYS = ["Order ID", "SKU ID"]


def get_ds_config(ds: DataSource | None) -> dict:
    return deepcopy(ds.config) if ds and ds.config else {}


def date_master_summary(cfg: dict) -> str:
    parts = []
    if cfg.get("order_file"):
        parts.append(f"[{cfg['order_file']}]")
    if cfg.get("order_sheet"):
        parts.append(cfg["order_sheet"])
    if cfg.get("order_date_col"):
        parts.append(cfg["order_date_col"])
    return " · ".join(parts) if parts else "未配置"


def apply_date_master(cfg: dict, body: dict) -> dict:
    out = deepcopy(cfg)
    for key in (
        "order_file",
        "order_sheet",
        "order_date_col",
        "order_date_format",
        "order_id_col",
        "sku_id_col",
        "daily_generate_at",
        "excel_template_file",
        "review_logistics_mode",
        "review_logistics_exclude_same_day_refund",
    ):
        if key in body:
            val = body[key]
            if isinstance(val, str):
                val = val.strip()
            out[key] = val or None
    if "review_logistics_per_order" in body:
        raw = body["review_logistics_per_order"]
        if raw is None or raw == "":
            out["review_logistics_per_order"] = None
        else:
            try:
                out["review_logistics_per_order"] = max(0.0, float(raw))
            except (TypeError, ValueError):
                out["review_logistics_per_order"] = None
    if "review_logistics_exclude_same_day_refund" in body:
        out["review_logistics_exclude_same_day_refund"] = bool(body["review_logistics_exclude_same_day_refund"])
    return out


def save_ds_config(db: Session, ds: DataSource, patch: dict) -> dict:
    cfg = apply_date_master(get_ds_config(ds), patch)
    if "review_order_ids" in patch:
        cfg["review_order_ids"] = list(patch["review_order_ids"] or [])
    if "review_orders" in patch:
        cfg["review_orders"] = list(patch["review_orders"] or [])
    if "sample_orders" in patch:
        cfg["sample_orders"] = list(patch["sample_orders"] or [])
    if "sample_order_ids" in patch:
        cfg["sample_order_ids"] = list(patch["sample_order_ids"] or [])
    ds.config = cfg
    db.commit()
    db.refresh(ds)
    return cfg


def serialize_ds_settings(ds: DataSource) -> dict:
    from app.services.review_import import (
        distinct_review_order_count,
        review_logistics_mode,
        review_logistics_per_order,
        review_logistics_exclude_same_day_refund,
        review_logistics_rule_summary,
    )

    cfg = get_ds_config(ds)
    store = ds.store
    reviews = cfg.get("review_orders") or []
    samples = cfg.get("sample_orders") or []
    return {
        "data_source_id": ds.id,
        "store_id": store.id if store else None,
        "store_name": store.name if store else "",
        "order_file": cfg.get("order_file") or "",
        "order_sheet": cfg.get("order_sheet") or "",
        "order_date_col": cfg.get("order_date_col") or "",
        "order_date_format": cfg.get("order_date_format") or "",
        "order_id_col": cfg.get("order_id_col") or "Order ID",
        "sku_id_col": cfg.get("sku_id_col") or "SKU ID",
        "daily_generate_at": cfg.get("daily_generate_at") or "",
        "excel_template_file": cfg.get("excel_template_file") or "",
        "review_order_count": len(reviews or cfg.get("review_order_ids") or []),
        "review_order_distinct": distinct_review_order_count(reviews),
        "review_logistics_mode": review_logistics_mode(cfg),
        "review_logistics_per_order": review_logistics_per_order(cfg),
        "review_logistics_exclude_same_day_refund": review_logistics_exclude_same_day_refund(cfg),
        "review_logistics_rule_summary": review_logistics_rule_summary(cfg),
        "sample_order_count": len(samples),
        "sample_order_distinct": len({str(r.get("order_id", "")).strip() for r in samples if r.get("order_id")}),
        "date_master_summary": date_master_summary(cfg),
    }
