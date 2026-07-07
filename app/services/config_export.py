"""报表配置 JSON 导出。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models import CatalogColumn, CatalogFile, CatalogSheet, DataSource, FieldMapping
from app.services.ds_settings import get_ds_config
from app.services.mapping_utils import is_formula_line, is_manual_line, mapping_label, mapping_line_code
from app.services.timezone import now_cst

EXPORT_VERSION = "1.0"

_SETTINGS_KEYS = (
    "order_file",
    "order_sheet",
    "order_date_col",
    "order_date_format",
    "order_id_col",
    "sku_id_col",
    "daily_generate_at",
    "sample_rule",
    "meta",
    "excel_template_file",
    "review_logistics_mode",
    "review_logistics_per_order",
    "review_logistics_exclude_same_day_refund",
)


def _serialize_part(part) -> dict[str, Any]:
    return {
        "sort_order": part.sort_order,
        "label": part.label,
        "ref_field_code": part.ref_field_code,
        "source_file_keyword": part.source_file_keyword,
        "sheet_name": part.sheet_name,
        "column_header": part.column_header,
        "aliases": list(part.aliases or []),
        "sources": list(part.sources or []),
        "combine_op": part.combine_op,
        "aggregation": part.aggregation,
        "dedup_keys": list(part.dedup_keys or []),
        "date_filter_column": part.date_filter_column,
        "date_format": part.date_format,
        "row_filters": list(part.row_filters or []),
        "exclude_sample": bool(part.exclude_sample),
        "exclude_review": bool(part.exclude_review),
        "exclude_same_day_refund": bool(getattr(part, "exclude_same_day_refund", False)),
        "join_to_orders": bool(part.join_to_orders),
        "join_keys": list(part.join_keys or []),
        "benchmark_keys": list(getattr(part, "benchmark_keys", None) or []),
        "only_sample": bool(getattr(part, "only_sample", False)),
    }


def _serialize_report_line(mapping: FieldMapping) -> dict[str, Any]:
    line_type = mapping.line_type or (
        "formula" if is_formula_line(mapping) else ("manual" if is_manual_line(mapping) else "fetch")
    )
    return {
        "line_type": line_type,
        "line_code": mapping_line_code(mapping),
        "label": mapping_label(mapping),
        "report_group": mapping.report_group,
        "sort_order": mapping.sort_order or 0,
        "expression": mapping.expression,
        "format_type": mapping.format_type or "usd",
        "is_highlight": bool(mapping.is_highlight),
        "description": mapping.description,
        "logical_field_code": mapping.logical_field.code if mapping.logical_field else None,
        "parts": [_serialize_part(p) for p in sorted(mapping.parts, key=lambda x: x.sort_order)],
    }


def _export_catalog(db: Session, data_source_id: int) -> dict[str, Any]:
    files_out: list[dict[str, Any]] = []
    rows = (
        db.query(CatalogFile)
        .options(
            joinedload(CatalogFile.sheets).joinedload(CatalogSheet.columns),
        )
        .filter(CatalogFile.data_source_id == data_source_id, CatalogFile.is_active.is_(True))
        .order_by(CatalogFile.id)
        .all()
    )
    for file in rows:
        sheets_out: list[dict[str, Any]] = []
        for sheet in sorted(file.sheets, key=lambda s: s.sheet_name):
            if not sheet.is_active:
                continue
            columns = [
                {
                    "header_name": col.header_name,
                    "db_column": col.db_column,
                    "column_aliases": list(col.column_aliases or []),
                    "data_type": col.data_type or "string",
                }
                for col in sorted(sheet.columns, key=lambda c: c.header_name)
                if col.is_active
            ]
            sheets_out.append(
                {
                    "sheet_name": sheet.sheet_name,
                    "fact_table": sheet.fact_table,
                    "columns": columns,
                }
            )
        files_out.append(
            {
                "keyword": file.keyword,
                "file_label": file.file_label,
                "file_name": file.file_name,
                "sheets": sheets_out,
            }
        )
    return {"files": files_out}


def _export_settings(cfg: dict, *, include_review_orders: bool) -> dict[str, Any]:
    out = {key: cfg.get(key) for key in _SETTINGS_KEYS if key in cfg}
    if include_review_orders:
        if cfg.get("review_orders"):
            out["review_orders"] = list(cfg["review_orders"])
        elif cfg.get("review_order_ids"):
            out["review_order_ids"] = list(cfg["review_order_ids"])
    return out


def build_config_export(
    db: Session,
    ds: DataSource,
    *,
    include_review_orders: bool = True,
) -> dict[str, Any]:
    cfg = get_ds_config(ds)
    store = ds.store
    mappings = (
        db.query(FieldMapping)
        .options(joinedload(FieldMapping.logical_field), joinedload(FieldMapping.parts))
        .filter(FieldMapping.data_source_id == ds.id)
        .order_by(FieldMapping.sort_order, FieldMapping.id)
        .all()
    )
    return {
        "export_version": EXPORT_VERSION,
        "exported_at": now_cst().isoformat(timespec="seconds"),
        "store": {
            "name": store.name if store else None,
            "platform": store.platform if store else None,
        },
        "data_source": {
            "name": ds.name,
            "platform": ds.platform,
            "description": ds.description,
        },
        "settings": _export_settings(cfg, include_review_orders=include_review_orders),
        "catalog": _export_catalog(db, ds.id),
        "report_lines": [_serialize_report_line(m) for m in mappings],
    }


def export_filename(ds: DataSource) -> str:
    """HTTP Content-Disposition 仅支持 ASCII，文件名用 ds id + 日期。"""
    stamp = now_cst().strftime("%Y%m%d")
    return f"autoreport-config_ds{ds.id}_{stamp}.json"
