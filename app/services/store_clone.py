"""店铺级配置克隆：Catalog + 报表行（含 parts）。"""

from __future__ import annotations

import copy

from sqlalchemy.orm import Session

from app.models import CatalogColumn, CatalogFile, CatalogSheet, FieldMapping, FieldMappingPart


def clone_catalog(db: Session, src_ds_id: int, dst_ds_id: int) -> int:
    if db.query(CatalogFile).filter(CatalogFile.data_source_id == dst_ds_id).count():
        return 0

    n = 0
    for src_file in db.query(CatalogFile).filter(CatalogFile.data_source_id == src_ds_id).all():
        dst_file = CatalogFile(
            data_source_id=dst_ds_id,
            keyword=src_file.keyword,
            file_label=src_file.file_label,
            file_name=src_file.file_name,
            is_active=src_file.is_active,
        )
        db.add(dst_file)
        db.flush()
        n += 1
        for src_sheet in src_file.sheets:
            dst_sheet = CatalogSheet(
                file_id=dst_file.id,
                sheet_name=src_sheet.sheet_name,
                fact_table=src_sheet.fact_table,
                is_active=src_sheet.is_active,
            )
            db.add(dst_sheet)
            db.flush()
            for src_col in src_sheet.columns:
                db.add(
                    CatalogColumn(
                        sheet_id=dst_sheet.id,
                        header_name=src_col.header_name,
                        db_column=src_col.db_column,
                        column_aliases=list(src_col.column_aliases or []),
                        data_type=src_col.data_type,
                        is_active=src_col.is_active,
                    )
                )
    db.commit()
    return n


def clone_field_mappings(db: Session, src_ds_id: int, dst_ds_id: int) -> int:
    if db.query(FieldMapping).filter(FieldMapping.data_source_id == dst_ds_id).count():
        return 0

    n = 0
    for src in (
        db.query(FieldMapping)
        .filter(FieldMapping.data_source_id == src_ds_id)
        .order_by(FieldMapping.sort_order, FieldMapping.id)
        .all()
    ):
        dst = FieldMapping(
            data_source_id=dst_ds_id,
            logical_field_id=src.logical_field_id,
            line_type=src.line_type,
            label=src.label,
            line_code=src.line_code,
            report_group=src.report_group,
            sort_order=src.sort_order,
            expression=src.expression,
            format_type=src.format_type,
            is_highlight=src.is_highlight,
            owner_id=src.owner_id,
            description=src.description,
            sheet_name=src.sheet_name,
            column_header=src.column_header,
            aliases=list(src.aliases or []),
            aggregation=src.aggregation,
        )
        db.add(dst)
        db.flush()
        n += 1
        for part in sorted(src.parts, key=lambda p: p.sort_order):
            db.add(
                FieldMappingPart(
                    mapping_id=dst.id,
                    sort_order=part.sort_order,
                    label=part.label,
                    source_file_keyword=part.source_file_keyword,
                    sheet_name=part.sheet_name,
                    column_header=part.column_header,
                    aliases=list(part.aliases or []),
                    combine_op=part.combine_op,
                    aggregation=part.aggregation,
                    dedup_keys=list(part.dedup_keys or []),
                    date_filter_column=part.date_filter_column,
                    date_format=part.date_format,
                    row_filters=copy.deepcopy(part.row_filters or []),
                    exclude_sample=part.exclude_sample,
                    exclude_review=part.exclude_review,
                    exclude_same_day_refund=getattr(part, "exclude_same_day_refund", False),
                    join_to_orders=part.join_to_orders,
                    join_keys=list(part.join_keys or []),
                    benchmark_keys=list(getattr(part, "benchmark_keys", None) or []),
                    only_sample=getattr(part, "only_sample", False),
                    sources=copy.deepcopy(part.sources or []),
                    ref_field_code=part.ref_field_code,
                )
            )
    db.commit()
    return n
