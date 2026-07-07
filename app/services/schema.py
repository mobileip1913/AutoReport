"""字段映射下拉：从 Catalog 目录表按需加载 文件 → Sheet → 列头。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import DataSource
from app.services import catalog_resolver


def query_schema(
    db: Session,
    data_source: DataSource,
    file_keyword: str | None = None,
    sheet_name: str | None = None,
) -> dict:
    if file_keyword and sheet_name:
        return {
            "columns": catalog_resolver.list_catalog_columns(
                db, data_source.id, file_keyword, sheet_name
            ),
        }
    if file_keyword:
        return {
            "sheets": catalog_resolver.list_catalog_sheets(db, data_source.id, file_keyword),
        }
    return {"files": catalog_resolver.list_catalog_files(db, data_source.id)}


def get_data_source_meta(db: Session, data_source: DataSource) -> dict:
    return {"files": catalog_resolver.list_catalog_files(db, data_source.id)}


def get_all_meta(db: Session, data_sources: list[DataSource]) -> dict[int, dict]:
    return {ds.id: get_data_source_meta(db, ds) for ds in data_sources}


def build_full_schema_snapshot(db: Session, data_source: DataSource) -> dict:
    """从 Catalog 导出 schema JSON（供 scripts/export_schema.py）。"""
    files_out = []
    merged: dict[str, set[str]] = {}
    for f in catalog_resolver.list_catalog_files(db, data_source.id):
        kw = f["keyword"]
        sheets_out: dict[str, list[str]] = {}
        for sh in catalog_resolver.list_catalog_sheets(db, data_source.id, kw):
            cols = catalog_resolver.list_catalog_columns(db, data_source.id, kw, sh)
            sheets_out[sh] = cols
            merged.setdefault(sh, set()).update(cols)
        files_out.append({**f, "sheets": sheets_out})
    return {"sheets": {k: sorted(v) for k, v in merged.items()}, "files": files_out}
