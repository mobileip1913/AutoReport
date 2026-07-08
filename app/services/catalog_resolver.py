"""逻辑 file/sheet/列头 → 物理表字段。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import CatalogColumn, CatalogFile, CatalogSheet


def catalog_file_display_label(file: CatalogFile) -> str:
    """UI 下拉用短名：优先 file_label / keyword，不从完整 file_name 截断。"""
    lbl = (file.file_label or "").strip()
    if lbl and lbl != file.file_name and not lbl.lower().endswith((".xlsx", ".xls")):
        return lbl
    kw = (file.keyword or "").strip()
    if kw:
        return kw
    name = re.sub(r"\.xlsx?$", "", file.file_name or "", flags=re.I)
    name = re.sub(r"_\d{8}(?:-\d{8})?$", "", name)
    parts = [p for p in name.split("_") if p]
    return parts[-1] if parts else (name or "文件")


@dataclass
class ResolvedColumn:
    file_id: int
    file_keyword: str
    file_name: str
    sheet_name: str
    fact_table: str
    header_name: str
    db_column: str
    column_aliases: list[str]


def has_catalog(db: Session, data_source_id: int) -> bool:
    return (
        db.query(CatalogFile.id)
        .filter(CatalogFile.data_source_id == data_source_id, CatalogFile.is_active.is_(True))
        .first()
        is not None
    )


def resolve_column(
    db: Session,
    data_source_id: int,
    file_keyword: str | None,
    sheet_name: str,
    header_name: str,
) -> ResolvedColumn | None:
    q = (
        db.query(CatalogColumn, CatalogSheet, CatalogFile)
        .join(CatalogSheet, CatalogColumn.sheet_id == CatalogSheet.id)
        .join(CatalogFile, CatalogSheet.file_id == CatalogFile.id)
        .filter(
            CatalogFile.data_source_id == data_source_id,
            CatalogFile.is_active.is_(True),
            CatalogSheet.is_active.is_(True),
            CatalogColumn.is_active.is_(True),
            CatalogSheet.sheet_name == sheet_name,
        )
    )
    if file_keyword:
        q = q.filter(CatalogFile.keyword == file_keyword)

    for col, sheet, file in q.all():
        names = [col.header_name, *(col.column_aliases or [])]
        if header_name in names:
            return ResolvedColumn(
                file_id=file.id,
                file_keyword=file.keyword,
                file_name=file.file_name,
                sheet_name=sheet.sheet_name,
                fact_table=sheet.fact_table,
                header_name=col.header_name,
                db_column=col.db_column,
                column_aliases=col.column_aliases or [],
            )
    return None


def list_catalog_files(db: Session, data_source_id: int) -> list[dict]:
    rows = (
        db.query(CatalogFile)
        .filter(CatalogFile.data_source_id == data_source_id, CatalogFile.is_active.is_(True))
        .order_by(CatalogFile.id)
        .all()
    )
    return [
        {
            "file_name": r.file_name,
            "keyword": r.keyword,
            "file_label": r.file_label,
            "label": catalog_file_display_label(r),
        }
        for r in rows
    ]


def list_catalog_sheets(db: Session, data_source_id: int, file_keyword: str) -> list[str]:
    rows = (
        db.query(CatalogSheet.sheet_name)
        .join(CatalogFile, CatalogSheet.file_id == CatalogFile.id)
        .filter(
            CatalogFile.data_source_id == data_source_id,
            CatalogFile.keyword == file_keyword,
            CatalogFile.is_active.is_(True),
            CatalogSheet.is_active.is_(True),
        )
        .all()
    )
    return sorted({name for (name,) in rows})


def list_catalog_columns(
    db: Session, data_source_id: int, file_keyword: str, sheet_name: str
) -> list[str]:
    rows = (
        db.query(CatalogColumn.header_name)
        .join(CatalogSheet, CatalogColumn.sheet_id == CatalogSheet.id)
        .join(CatalogFile, CatalogSheet.file_id == CatalogFile.id)
        .filter(
            CatalogFile.data_source_id == data_source_id,
            CatalogFile.keyword == file_keyword,
            CatalogSheet.sheet_name == sheet_name,
            CatalogFile.is_active.is_(True),
            CatalogSheet.is_active.is_(True),
            CatalogColumn.is_active.is_(True),
        )
        .all()
    )
    return sorted({name for (name,) in rows if name})
