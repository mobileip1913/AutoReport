import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DataSource, FieldMapping, FieldMappingPart, LogicalField, ReportTemplate, TemplateStatus
from app.services.mapping_utils import is_formula_line, mapping_label, mapping_line_code, slug_line_code
from app.services.report_engine import generate_report, generate_report_for_data_source
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
    label: str | None = None
    line_code: str | None = None
    line_type: str = "fetch"
    report_group: str | None = None
    sort_order: int | None = None
    expression: str | None = None
    format_type: str | None = None
    is_highlight: bool = False
    description: str | None = None
    parts: list[MappingPartIn] = Field(default_factory=list)


class MappingCreateFull(MappingSave):
    data_source_id: int
    logical_field_id: int | None = None


class FormulaSave(BaseModel):
    label: str
    line_code: str | None = None
    report_group: str | None = None
    sort_order: int = 0
    expression: str
    format_type: str = "usd"
    is_highlight: bool = False
    description: str | None = None


class FormulaCreate(FormulaSave):
    data_source_id: int


def _serialize_mapping(m: FieldMapping) -> dict:
    code = mapping_line_code(m)
    return {
        "id": m.id,
        "data_source_id": m.data_source_id,
        "logical_field_id": m.logical_field_id,
        "logical_field_name": m.logical_field.name if m.logical_field else None,
        "logical_field_code": m.logical_field.code if m.logical_field else None,
        "data_source_name": m.data_source.name,
        "line_type": m.line_type or ("formula" if is_formula_line(m) else "fetch"),
        "label": mapping_label(m),
        "line_code": code,
        "report_group": m.report_group,
        "sort_order": m.sort_order or 0,
        "expression": m.expression,
        "format_type": m.format_type or "usd",
        "is_highlight": bool(m.is_highlight),
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


def _apply_report_fields(mapping: FieldMapping, body: MappingSave, db: Session, ds_id: int):
    if body.label is not None:
        mapping.label = body.label.strip() or mapping.label
    if body.line_code is not None:
        mapping.line_code = body.line_code.strip() or mapping.line_code
    if body.line_type:
        mapping.line_type = body.line_type
    if body.report_group is not None:
        mapping.report_group = body.report_group.strip() or None
    if body.sort_order is not None:
        mapping.sort_order = body.sort_order
    if body.expression is not None:
        mapping.expression = body.expression.strip() or None
    if body.format_type:
        mapping.format_type = body.format_type
    mapping.is_highlight = body.is_highlight
    if body.description is not None:
        mapping.description = body.description
    if not mapping.line_code:
        used = {
            mapping_line_code(x)
            for x in db.query(FieldMapping).filter(FieldMapping.data_source_id == ds_id).all()
            if x.id != mapping.id and mapping_line_code(x)
        }
        base = mapping.label or "line"
        mapping.line_code = slug_line_code(base, used)


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
    data_source_id: int = Form(...),
    report_date: str = Form(...),
    store_name: str = Form(...),
    template_id: int | None = Form(None),
    is_test: bool = Form(False),
    db: Session = Depends(get_db),
):
    if template_id:
        template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")
        if not is_test and template.status != TemplateStatus.PUBLISHED:
            raise HTTPException(status_code=400, detail="正式生成需使用已发布模板")
        run = generate_report(db, template, data_source_id, report_date, store_name, is_test=is_test)
    else:
        run = generate_report_for_data_source(
            db, data_source_id, report_date, store_name, is_test=is_test
        )
    return {"run_id": run.id, "status": run.status}


@router.get("/data-sources/{data_source_id}/report-lines")
def list_report_lines(data_source_id: int, db: Session = Depends(get_db)):
    ds = db.query(DataSource).filter(DataSource.id == data_source_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    rows = (
        db.query(FieldMapping)
        .filter(FieldMapping.data_source_id == data_source_id)
        .order_by(FieldMapping.sort_order, FieldMapping.id)
        .all()
    )
    return {
        "data_source_id": data_source_id,
        "lines": [_serialize_mapping(m) for m in rows],
    }


@router.get("/data-sources/{data_source_id}/mapped-fields")
def data_source_mapped_fields(
    data_source_id: int,
    exclude: str | None = None,
    db: Session = Depends(get_db),
):
    """同数据源下已配置取数行，供「已有字段复用」与公式引用。"""
    mappings = (
        db.query(FieldMapping)
        .filter(FieldMapping.data_source_id == data_source_id)
        .order_by(FieldMapping.sort_order, FieldMapping.id)
        .all()
    )
    fields = []
    for m in mappings:
        if is_formula_line(m):
            continue
        if not (m.parts or (m.sheet_name and m.column_header)):
            code = mapping_line_code(m)
            if exclude and code == exclude:
                continue
            fields.append({"code": code, "name": mapping_label(m)})
            continue
        code = mapping_line_code(m)
        if exclude and code == exclude:
            continue
        fields.append({"code": code, "name": mapping_label(m)})
    return {"data_source_id": data_source_id, "fields": fields}


@router.get("/data-sources/{data_source_id}/schema")
def data_source_schema(
    data_source_id: int,
    file: str | None = None,
    sheet: str | None = None,
    db: Session = Depends(get_db),
):
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
    if is_formula_line(mapping) or (body.line_type or "").lower() == "formula":
        raise HTTPException(status_code=400, detail="公式行请使用 /api/formula-lines 接口")
    if not body.parts:
        raise HTTPException(status_code=400, detail="至少配置一条取数规则")
    _apply_report_fields(mapping, body, db, mapping.data_source_id)
    mapping.line_type = "fetch"
    _apply_parts(mapping, body.parts, db)
    db.commit()
    db.refresh(mapping)
    return _serialize_mapping(mapping)


@router.post("/mappings")
def create_mapping_api(body: MappingCreateFull, db: Session = Depends(get_db)):
    if (body.line_type or "fetch").lower() == "formula":
        raise HTTPException(status_code=400, detail="公式行请使用 POST /api/formula-lines")
    if not body.parts:
        raise HTTPException(status_code=400, detail="至少配置一条取数规则")

    line_code = (body.line_code or "").strip()
    if not line_code and body.logical_field_id:
        lf = db.query(LogicalField).filter(LogicalField.id == body.logical_field_id).first()
        line_code = lf.code if lf else ""
    if line_code:
        exists = (
            db.query(FieldMapping)
            .filter(
                FieldMapping.data_source_id == body.data_source_id,
                FieldMapping.line_code == line_code,
            )
            .first()
        )
        if exists:
            raise HTTPException(status_code=400, detail=f"line_code {line_code} 已存在")

    mapping = FieldMapping(
        data_source_id=body.data_source_id,
        logical_field_id=body.logical_field_id,
        line_type="fetch",
    )
    db.add(mapping)
    db.flush()
    _apply_report_fields(mapping, body, db, body.data_source_id)
    _apply_parts(mapping, body.parts, db)
    db.commit()
    db.refresh(mapping)
    return _serialize_mapping(mapping)


@router.post("/formula-lines")
def create_formula_line(body: FormulaCreate, db: Session = Depends(get_db)):
    ds = db.query(DataSource).filter(DataSource.id == body.data_source_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    line_code = (body.line_code or "").strip()
    if not line_code:
        used = {mapping_line_code(m) for m in db.query(FieldMapping).filter_by(data_source_id=body.data_source_id)}
        line_code = slug_line_code(body.label, used)
    exists = (
        db.query(FieldMapping)
        .filter(FieldMapping.data_source_id == body.data_source_id, FieldMapping.line_code == line_code)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail=f"line_code {line_code} 已存在")

    mapping = FieldMapping(
        data_source_id=body.data_source_id,
        line_type="formula",
        label=body.label.strip(),
        line_code=line_code,
        report_group=(body.report_group or "").strip() or None,
        sort_order=body.sort_order,
        expression=body.expression.strip(),
        format_type=body.format_type,
        is_highlight=body.is_highlight,
        description=body.description,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return _serialize_mapping(mapping)


@router.put("/formula-lines/{mapping_id}")
def save_formula_line(mapping_id: int, body: FormulaSave, db: Session = Depends(get_db)):
    mapping = db.query(FieldMapping).filter(FieldMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="公式行不存在")
    mapping.line_type = "formula"
    mapping.label = body.label.strip()
    if body.line_code:
        mapping.line_code = body.line_code.strip()
    mapping.report_group = (body.report_group or "").strip() or None
    mapping.sort_order = body.sort_order
    mapping.expression = body.expression.strip()
    mapping.format_type = body.format_type
    mapping.is_highlight = body.is_highlight
    mapping.description = body.description
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
