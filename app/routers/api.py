import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DataSource, FieldMapping, FieldMappingPart, LogicalField, ReportTemplate, TemplateStatus
from app.services.report_engine import generate_report
from app.services.schema import get_data_source_meta

router = APIRouter(prefix="/api", tags=["api"])


class RowFilterIn(BaseModel):
    column: str
    op: str = "eq"
    values: list[str] = Field(default_factory=list)


class MappingSourceIn(BaseModel):
    source_file_keyword: str | None = None
    sheet_name: str
    column_header: str
    combine_op: str = "add"


class MappingPartIn(BaseModel):
    label: str | None = None
    ref_field_code: str | None = None
    source_file_keyword: str | None = None
    sheet_name: str = ""
    column_header: str = ""
    aliases: list[str] = Field(default_factory=list)
    sources: list[MappingSourceIn] = Field(default_factory=list)
    combine_op: str = "add"
    aggregation: str = "sum"
    dedup_keys: list[str] = Field(default_factory=list)
    date_filter_column: str | None = None
    date_format: str | None = None
    row_filters: list[RowFilterIn] = Field(default_factory=list)
    exclude_sample: bool = False
    exclude_review: bool = False
    join_to_orders: bool = False


class MappingSave(BaseModel):
    description: str | None = None
    parts: list[MappingPartIn]


class MappingCreateFull(BaseModel):
    data_source_id: int
    logical_field_id: int
    description: str | None = None
    parts: list[MappingPartIn]


def _serialize_mapping(m: FieldMapping) -> dict:
    return {
        "id": m.id,
        "data_source_id": m.data_source_id,
        "logical_field_id": m.logical_field_id,
        "logical_field_name": m.logical_field.name,
        "logical_field_code": m.logical_field.code,
        "data_source_name": m.data_source.name,
        "description": m.description,
        "parts": [
            {
                "id": p.id,
                "sort_order": p.sort_order,
                "label": p.label,
                "source_file_keyword": p.source_file_keyword,
                "sheet_name": p.sheet_name,
                "column_header": p.column_header,
                "aliases": p.aliases or [],
                "sources": p.sources or [],
                "ref_field_code": p.ref_field_code,
                "combine_op": p.combine_op,
                "aggregation": p.aggregation,
                "dedup_keys": p.dedup_keys or [],
                "date_filter_column": p.date_filter_column,
                "date_format": p.date_format,
                "row_filters": p.row_filters or [],
                "exclude_sample": bool(p.exclude_sample),
                "exclude_review": bool(p.exclude_review),
                "join_to_orders": bool(p.join_to_orders),
            }
            for p in sorted(m.parts, key=lambda x: x.sort_order)
        ],
    }


def _apply_parts(mapping: FieldMapping, parts: list[MappingPartIn], db: Session):
    db.query(FieldMappingPart).filter(FieldMappingPart.mapping_id == mapping.id).delete()
    for idx, part in enumerate(parts):
        ref_code = (part.ref_field_code or "").strip() or None
        if ref_code:
            db.add(
                FieldMappingPart(
                    mapping_id=mapping.id,
                    sort_order=idx,
                    label=part.label,
                    ref_field_code=ref_code,
                    sheet_name="",
                    column_header="",
                    aliases=[],
                    sources=[],
                    combine_op=part.combine_op or "add",
                    aggregation="sum",
                    dedup_keys=[],
                )
            )
            continue
        sources = [s.model_dump() for s in part.sources] if part.sources else []
        first = sources[0] if sources else None
        sheet_name = (first["sheet_name"] if first else part.sheet_name).strip()
        column_header = (first["column_header"] if first else part.column_header).strip()
        file_kw = (first.get("source_file_keyword") if first else part.source_file_keyword) or ""
        db.add(
            FieldMappingPart(
                mapping_id=mapping.id,
                sort_order=idx,
                label=part.label,
                source_file_keyword=(file_kw or "").strip() or None,
                sheet_name=sheet_name,
                column_header=column_header,
                aliases=part.aliases,
                sources=sources,
                combine_op=part.combine_op or "add",
                aggregation=part.aggregation or "sum",
                dedup_keys=part.dedup_keys,
                date_filter_column=(part.date_filter_column or "").strip() or None,
                date_format=(part.date_format or "").strip() or None,
                row_filters=[f.model_dump() for f in part.row_filters],
                exclude_sample=part.exclude_sample,
                exclude_review=part.exclude_review,
                join_to_orders=part.join_to_orders,
            )
        )


@router.post("/import")
async def import_excel(
    data_source_id: int = Form(...),
    report_date: str = Form(...),
    store_name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    raise HTTPException(
        status_code=410,
        detail="Web Excel 导入已停用。请使用离线 ETL：python scripts/import_meichong.py",
    )


@router.post("/generate")
def generate(
    template_id: int = Form(...),
    data_source_id: int = Form(...),
    report_date: str = Form(...),
    store_name: str = Form(...),
    is_test: bool = Form(False),
    db: Session = Depends(get_db),
):
    template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    if not is_test and template.status != TemplateStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="正式生成需使用已发布模板")

    run = generate_report(db, template, data_source_id, report_date, store_name, is_test=is_test)
    return {"run_id": run.id, "status": run.status}


@router.get("/data-sources/{data_source_id}/mapped-fields")
def data_source_mapped_fields(
    data_source_id: int,
    exclude: str | None = None,
    db: Session = Depends(get_db),
):
    """同数据源下已配置映射的逻辑字段，供「已有字段复用」下拉。"""
    mappings = (
        db.query(FieldMapping)
        .filter(FieldMapping.data_source_id == data_source_id)
        .all()
    )
    fields = []
    for m in mappings:
        if not (m.parts or (m.sheet_name and m.column_header)):
            continue
        code = m.logical_field.code
        if exclude and code == exclude:
            continue
        fields.append({"code": code, "name": m.logical_field.name})
    return {"data_source_id": data_source_id, "fields": fields}


@router.get("/data-sources/{data_source_id}/schema")
def data_source_schema(
    data_source_id: int,
    file: str | None = None,
    sheet: str | None = None,
    db: Session = Depends(get_db),
):
    """按需加载：无参数=文件列表；file=Sheet 列表；file+sheet=列头列表。"""
    from app.services.schema import query_schema

    ds = db.query(DataSource).filter(DataSource.id == data_source_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return {"data_source_id": data_source_id, **query_schema(db, ds, file, sheet)}


@router.get("/mappings/{mapping_id}")
def get_mapping(mapping_id: int, db: Session = Depends(get_db)):
    mapping = db.query(FieldMapping).filter(FieldMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="映射不存在")
    return _serialize_mapping(mapping)


@router.put("/mappings/{mapping_id}")
def save_mapping(mapping_id: int, body: MappingSave, db: Session = Depends(get_db)):
    mapping = db.query(FieldMapping).filter(FieldMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="映射不存在")
    if not body.parts:
        raise HTTPException(status_code=400, detail="至少配置一条取数规则")
    mapping.description = body.description
    _apply_parts(mapping, body.parts, db)
    db.commit()
    db.refresh(mapping)
    return _serialize_mapping(mapping)


@router.post("/mappings")
def create_mapping_api(body: MappingCreateFull, db: Session = Depends(get_db)):
    exists = (
        db.query(FieldMapping)
        .filter(
            FieldMapping.data_source_id == body.data_source_id,
            FieldMapping.logical_field_id == body.logical_field_id,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="该数据源下此逻辑字段已有映射")
    if not body.parts:
        raise HTTPException(status_code=400, detail="至少配置一条取数规则")

    mapping = FieldMapping(
        data_source_id=body.data_source_id,
        logical_field_id=body.logical_field_id,
        description=body.description,
    )
    db.add(mapping)
    db.flush()
    _apply_parts(mapping, body.parts, db)
    db.commit()
    db.refresh(mapping)
    return _serialize_mapping(mapping)


@router.delete("/mappings/{mapping_id}")
def delete_mapping_api(mapping_id: int, db: Session = Depends(get_db)):
    mapping = db.query(FieldMapping).filter(FieldMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="映射不存在")
    db.delete(mapping)
    db.commit()
    return {"status": "deleted"}
