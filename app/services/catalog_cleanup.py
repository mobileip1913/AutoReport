"""清理非生产 Catalog（fact_mc_*、Statements、Payments 等）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import CatalogColumn, CatalogFile, CatalogSheet, DataSource
from app.services.production_schema import is_production_fact_table

_LEGACY_SHEET_NAMES = frozenset({"Statements", "Payments"})


def _is_legacy_sheet(sheet: CatalogSheet) -> bool:
    if sheet.sheet_name in _LEGACY_SHEET_NAMES:
        return True
    if sheet.fact_table and not is_production_fact_table(sheet.fact_table):
        return True
    return False


def cleanup_legacy_fact_catalog(db: Session, data_source_id: int | None = None) -> int:
    """删除 legacy Catalog Sheet/Column，返回删除的 Sheet 数。"""
    q = db.query(CatalogSheet).join(CatalogFile, CatalogSheet.file_id == CatalogFile.id)
    if data_source_id is not None:
        q = q.filter(CatalogFile.data_source_id == data_source_id)
    removed = 0
    for sheet in q.all():
        if not _is_legacy_sheet(sheet):
            continue
        db.query(CatalogColumn).filter(CatalogColumn.sheet_id == sheet.id).delete(synchronize_session=False)
        db.delete(sheet)
        removed += 1
    if removed:
        db.commit()
    return removed


def ensure_production_fact_schema(db: Session, data_source_id: int) -> None:
    """数据源 config 固定为 production。"""
    ds = db.query(DataSource).filter(DataSource.id == data_source_id).first()
    if not ds:
        return
    cfg = dict(ds.config or {})
    if cfg.get("fact_schema") != "production":
        cfg["fact_schema"] = "production"
        ds.config = cfg
        db.commit()
