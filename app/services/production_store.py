"""生产店铺主表 `eb_overseas_store` 查询与 AutoReport `stores` 同步。"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.database import engine
from app.models import DataSource, Store
from app.services.seed import MEICHONG_SOURCE_NAME, MEICHONG_STORE

PRODUCTION_STORE_TABLE = "eb_overseas_store"


def production_store_table_exists() -> bool:
    return PRODUCTION_STORE_TABLE in inspect(engine).get_table_names()


def lookup_production_store(store_name: str) -> dict | None:
    """按店铺名查生产主表，返回 {id, name, shop_code, ...}。"""
    if not production_store_table_exists():
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text(
                f"SELECT id, name, shop_code, product_id, region_id, platform_id "
                f"FROM `{PRODUCTION_STORE_TABLE}` WHERE name = :name LIMIT 1"
            ),
            {"name": store_name},
        ).mappings().first()
    return dict(row) if row else None


def sync_store_production_ids(
    db: Session,
    *,
    store_name: str = MEICHONG_STORE,
    data_source_name: str = MEICHONG_SOURCE_NAME,
) -> dict | None:
    """将生产 `eb_overseas_store` 的 id/shop_code 写入 AutoReport stores 与 data_sources.config。"""
    prod = lookup_production_store(store_name)
    if not prod:
        return None

    store_id = int(prod["id"])
    shop_code = prod.get("shop_code") or None

    ds = db.query(DataSource).filter(DataSource.name == data_source_name).first()
    if ds:
        cfg = dict(ds.config or {})
        cfg["fact_schema"] = cfg.get("fact_schema") or "production"
        cfg["production_store_id"] = store_id
        cfg["shop_code"] = shop_code
        ds.config = cfg

    store = None
    if ds:
        store = db.query(Store).filter(Store.data_source_id == ds.id).first()
    if not store:
        store = db.query(Store).filter(Store.name == store_name).first()
    if store:
        store.production_store_id = store_id
        store.shop_code = shop_code

    db.commit()
    return {"production_store_id": store_id, "shop_code": shop_code, "store_name": store_name}
