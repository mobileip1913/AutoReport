import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import DataSource, FieldMapping, FieldMappingPart, LogicalField, ReportTemplate, TemplateStatus
from app.services.account_context import assert_data_source_access, assert_mapping_access
from app.services.mapping_utils import (
    default_expression,
    is_formula_line,
    is_manual_line,
    mapping_label,
    mapping_line_code,
    mapping_source_file_keywords,
    slug_line_code,
)
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
    row_filters: list[RowFilterIn] = Field(default_factory=list)


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
    exclude_same_day_refund: bool = False
    join_to_orders: bool = False
    join_keys: list[str] = Field(default_factory=list)
    benchmark_keys: list[str] = Field(default_factory=list)
    only_sample: bool = False


class MappingSave(BaseModel):
    label: str | None = None
    line_code: str | None = None
    line_type: str = "fetch"  # fetch(计算) | per_order(每单金额) | manual(占位)
    report_group: str | None = None
    sort_order: int | None = None
    expression: str | None = None
    format_type: str | None = None
    is_highlight: bool = False
    description: str | None = None
    per_order_amount: float | None = None
    per_order_basis: str | None = None
    ratio_percent: float | None = None
    ratio_base_code: str | None = None
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
        "per_order_amount": m.per_order_amount,
        "per_order_basis": m.per_order_basis or "valid_orders",
        "ratio_percent": m.ratio_percent,
        "ratio_base_code": m.ratio_base_code,
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
                "exclude_same_day_refund": bool(getattr(p, "exclude_same_day_refund", False)),
                "join_to_orders": bool(p.join_to_orders),
                "join_keys": p.join_keys or [],
                "benchmark_keys": getattr(p, "benchmark_keys", None) or [],
                "only_sample": bool(getattr(p, "only_sample", False)),
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
                    benchmark_keys=[k.strip() for k in (part.benchmark_keys or []) if k and str(k).strip()],
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
                exclude_same_day_refund=part.exclude_same_day_refund,
                join_to_orders=part.join_to_orders,
                join_keys=[k.strip() for k in (part.join_keys or []) if k and str(k).strip()],
                benchmark_keys=[k.strip() for k in (part.benchmark_keys or []) if k and str(k).strip()],
                only_sample=part.only_sample,
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
def list_report_lines(data_source_id: int, request: Request, db: Session = Depends(get_db)):
    assert_data_source_access(request, db, data_source_id)
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
    request: Request,
    exclude: str | None = None,
    db: Session = Depends(get_db),
):
    assert_data_source_access(request, db, data_source_id)
    """同数据源下已配置取数行，供「已有字段复用」与公式引用。"""
    from app.services.mapping_utils import is_report_line

    mappings = (
        db.query(FieldMapping)
        .filter(FieldMapping.data_source_id == data_source_id)
        .all()
    )
    # 报表指标行（指标名称）在前，基础取数字段（字段名称）在后
    mappings.sort(key=lambda m: (0 if is_report_line(m) else 1, m.sort_order or 0, m.id))
    fields = []
    for m in mappings:
        if is_formula_line(m) or is_manual_line(m):
            continue
        code = mapping_line_code(m)
        if exclude and code == exclude:
            continue
        fields.append({
            "code": code,
            "name": mapping_label(m),
            "mapping_id": m.id,
            "configured": bool(m.parts or (m.sheet_name and m.column_header)),
            "source_files": mapping_source_file_keywords(m),
        })
    return {"data_source_id": data_source_id, "fields": fields}


@router.get("/data-sources/{data_source_id}/catalog")
def data_source_catalog_tree(data_source_id: int, request: Request, db: Session = Depends(get_db)):
    assert_data_source_access(request, db, data_source_id)
    """完整 Catalog 目录：文件 → Sheet → 列头（供财务浏览 / 配置时选取）。"""
    from app.services.schema import build_full_schema_snapshot

    ds = db.query(DataSource).filter(DataSource.id == data_source_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return {"data_source_id": data_source_id, **build_full_schema_snapshot(db, ds)}


@router.get("/data-sources/{data_source_id}/schema")
def data_source_schema(
    data_source_id: int,
    request: Request,
    file: str | None = None,
    sheet: str | None = None,
    db: Session = Depends(get_db),
):
    assert_data_source_access(request, db, data_source_id)
    from app.services.schema import query_schema

    ds = db.query(DataSource).filter(DataSource.id == data_source_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return {"data_source_id": data_source_id, **query_schema(db, ds, file, sheet)}


@router.get("/mappings/{mapping_id}")
def get_mapping(mapping_id: int, request: Request, db: Session = Depends(get_db)):
    mapping = db.query(FieldMapping).filter(FieldMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="映射不存在")
    assert_mapping_access(request, db, mapping)
    return _serialize_mapping(mapping)


def _clear_special_fields(mapping: FieldMapping):
    mapping.per_order_amount = None
    mapping.per_order_basis = None
    mapping.ratio_percent = None
    mapping.ratio_base_code = None


def _apply_fetch_kind(mapping: FieldMapping, body: MappingSave, db: Session):
    """按取数方式落库：per_order(每单金额) | ratio(按比例) | manual(占位) | fetch(计算/复用)。"""
    kind = (body.line_type or "fetch").lower()
    if kind == "per_order":
        if body.per_order_amount is None:
            raise HTTPException(status_code=400, detail="请填写每单金额")
        _clear_special_fields(mapping)
        mapping.line_type = "per_order"
        mapping.per_order_amount = max(0.0, float(body.per_order_amount))
        mapping.per_order_basis = (
            "review_orders" if (body.per_order_basis or "").strip() == "review_orders" else "valid_orders"
        )
        _apply_parts(mapping, [], db)
    elif kind == "ratio":
        base = (body.ratio_base_code or "").strip()
        if not base:
            raise HTTPException(status_code=400, detail="请选择按比例的基准字段")
        if body.ratio_percent is None:
            raise HTTPException(status_code=400, detail="请填写比例")
        _clear_special_fields(mapping)
        mapping.line_type = "ratio"
        mapping.ratio_base_code = base
        mapping.ratio_percent = float(body.ratio_percent)
        _apply_parts(mapping, [], db)
    elif kind == "manual":
        _clear_special_fields(mapping)
        mapping.line_type = "manual"
        _apply_parts(mapping, [], db)
    else:
        if not body.parts:
            raise HTTPException(status_code=400, detail="至少配置一条取数规则")
        _clear_special_fields(mapping)
        mapping.line_type = "fetch"
        _apply_parts(mapping, body.parts, db)


@router.put("/mappings/{mapping_id}")
def save_mapping(mapping_id: int, body: MappingSave, request: Request, db: Session = Depends(get_db)):
    mapping = db.query(FieldMapping).filter(FieldMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="映射不存在")
    assert_mapping_access(request, db, mapping)
    if is_formula_line(mapping) or (body.line_type or "").lower() == "formula":
        raise HTTPException(status_code=400, detail="公式行请使用 /api/formula-lines 接口")
    _apply_report_fields(mapping, body, db, mapping.data_source_id)
    _apply_fetch_kind(mapping, body, db)
    db.commit()
    db.refresh(mapping)
    return _serialize_mapping(mapping)


@router.post("/mappings")
def create_mapping_api(body: MappingCreateFull, request: Request, db: Session = Depends(get_db)):
    assert_data_source_access(request, db, body.data_source_id)
    if (body.line_type or "fetch").lower() == "formula":
        raise HTTPException(status_code=400, detail="公式行请使用 POST /api/formula-lines")

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
    _apply_fetch_kind(mapping, body, db)
    db.commit()
    db.refresh(mapping)
    return _serialize_mapping(mapping)


@router.post("/formula-lines")
def create_formula_line(body: FormulaCreate, request: Request, db: Session = Depends(get_db)):
    assert_data_source_access(request, db, body.data_source_id)
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
def save_formula_line(mapping_id: int, body: FormulaSave, request: Request, db: Session = Depends(get_db)):
    mapping = db.query(FieldMapping).filter(FieldMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="公式行不存在")
    assert_mapping_access(request, db, mapping)
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
def delete_mapping_api(mapping_id: int, request: Request, db: Session = Depends(get_db)):
    mapping = db.query(FieldMapping).filter(FieldMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="映射不存在")
    assert_mapping_access(request, db, mapping)
    db.delete(mapping)
    db.commit()
    return {"status": "deleted"}


class ReportValueUpdateIn(BaseModel):
    raw_value: float | None = None
    clear_override: bool = False


class QuickReportFieldIn(BaseModel):
    label: str
    format_type: str = "usd"
    run_id: int | None = None


class ReorderReportFieldsIn(BaseModel):
    mapping_ids: list[int]


class MappingLabelPatchIn(BaseModel):
    label: str
    run_id: int | None = None


@router.post("/data-sources/{data_source_id}/report-fields")
def quick_add_report_field(
    data_source_id: int,
    body: QuickReportFieldIn,
    request: Request,
    db: Session = Depends(get_db),
):
    assert_data_source_access(request, db, data_source_id)
    label = (body.label or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="请填写字段名称")

    used = {
        mapping_line_code(m)
        for m in db.query(FieldMapping).filter(FieldMapping.data_source_id == data_source_id).all()
    }
    max_sort = (
        db.query(FieldMapping.sort_order)
        .filter(FieldMapping.data_source_id == data_source_id)
        .order_by(FieldMapping.sort_order.desc())
        .limit(1)
        .scalar()
    ) or 0

    mapping = FieldMapping(
        data_source_id=data_source_id,
        line_type="fetch",
        label=label,
        line_code=slug_line_code(label, used),
        sort_order=int(max_sort) + 10,
        report_group="报表字段",
        format_type=body.format_type or "usd",
    )
    db.add(mapping)
    db.flush()

    if body.run_id:
        from app.models import ReportRun, ReportValue
        from app.services.formula import format_value

        run = db.query(ReportRun).filter(ReportRun.id == body.run_id).first()
        if run and (run.data_source_id == data_source_id or not run.data_source_id):
            fmt = mapping.format_type or "usd"
            db.add(
                ReportValue(
                    report_run_id=run.id,
                    mapping_id=mapping.id,
                    line_code=mapping.line_code,
                    line_label=label,
                    expression=default_expression(mapping),
                    raw_value=0.0,
                    computed_raw_value=0.0,
                    display_value=format_value(0.0, fmt),
                    is_overridden=False,
                    sort_order=mapping.sort_order or 0,
                    report_group=mapping.report_group,
                )
            )

    db.commit()
    db.refresh(mapping)
    return _serialize_mapping(mapping)


@router.put("/data-sources/{data_source_id}/report-fields/order")
def reorder_report_fields(
    data_source_id: int,
    body: ReorderReportFieldsIn,
    request: Request,
    db: Session = Depends(get_db),
):
    assert_data_source_access(request, db, data_source_id)
    if not body.mapping_ids:
        raise HTTPException(status_code=400, detail="排序列表为空")

    by_id = {
        m.id: m
        for m in db.query(FieldMapping)
        .filter(FieldMapping.data_source_id == data_source_id)
        .all()
    }
    for i, mid in enumerate(body.mapping_ids):
        m = by_id.get(mid)
        if not m:
            raise HTTPException(status_code=400, detail=f"字段 {mid} 不存在")
        m.sort_order = (i + 1) * 10
    db.commit()
    return {"status": "ok", "count": len(body.mapping_ids)}


@router.patch("/mappings/{mapping_id}/label")
def patch_mapping_label(
    mapping_id: int,
    body: MappingLabelPatchIn,
    request: Request,
    db: Session = Depends(get_db),
):
    from app.models import ReportValue

    mapping = db.query(FieldMapping).filter(FieldMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="映射不存在")
    assert_mapping_access(request, db, mapping)
    label = (body.label or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="名称不能为空")
    mapping.label = label
    if body.run_id:
        for rv in (
            db.query(ReportValue)
            .filter(ReportValue.report_run_id == body.run_id, ReportValue.mapping_id == mapping_id)
            .all()
        ):
            rv.line_label = label
    db.commit()
    db.refresh(mapping)
    return {"id": mapping.id, "label": mapping.label, "line_code": mapping_line_code(mapping)}


@router.patch("/report-runs/{run_id}/values/{value_id}")
def patch_report_value(
    run_id: int,
    value_id: int,
    body: ReportValueUpdateIn,
    request: Request,
    db: Session = Depends(get_db),
):
    from app.models import ReportRun, ReportValue
    from app.services.formula import format_value

    run = db.query(ReportRun).filter(ReportRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="报表不存在")
    if run.data_source_id:
        assert_data_source_access(request, db, run.data_source_id)

    rv = (
        db.query(ReportValue)
        .filter(ReportValue.id == value_id, ReportValue.report_run_id == run_id)
        .first()
    )
    if not rv:
        raise HTTPException(status_code=404, detail="字段不存在")

    mapping = None
    if rv.mapping_id:
        mapping = db.query(FieldMapping).filter(FieldMapping.id == rv.mapping_id).first()
    fmt = (mapping.format_type if mapping else "usd") or "usd"
    is_manual = is_manual_line(mapping) if mapping else rv.line_label in {
        "利润", "总利润", "利润(估算)", "总利润(估算)"
    }

    if body.clear_override:
        if rv.computed_raw_value is not None:
            rv.raw_value = rv.computed_raw_value
            rv.display_value = format_value(rv.computed_raw_value, fmt)
        else:
            rv.raw_value = None
            rv.display_value = ""
        rv.is_overridden = False
    elif body.raw_value is not None:
        rv.raw_value = float(body.raw_value)
        rv.display_value = format_value(rv.raw_value, fmt)
        computed = rv.computed_raw_value
        if is_manual:
            rv.is_overridden = False
        else:
            rv.is_overridden = computed is None or abs(float(computed) - rv.raw_value) > 1e-9
    else:
        rv.raw_value = None
        rv.display_value = ""
        rv.is_overridden = False if is_manual else rv.computed_raw_value is not None

    db.commit()
    db.refresh(rv)
    return {
        "id": rv.id,
        "raw_value": rv.raw_value,
        "display_value": rv.display_value,
        "is_overridden": rv.is_overridden,
        "computed_display": format_value(rv.computed_raw_value, fmt) if rv.computed_raw_value is not None else "",
    }


class DataSourceSettingsIn(BaseModel):
    order_file: str | None = None
    order_sheet: str | None = None
    order_date_col: str | None = None
    order_date_format: str | None = None
    order_id_col: str | None = None
    sku_id_col: str | None = None
    daily_generate_at: str | None = None
    excel_template_file: str | None = None
    review_logistics_mode: str | None = None
    review_logistics_per_order: float | None = None
    review_logistics_exclude_same_day_refund: bool | None = None


@router.get("/data-sources/{data_source_id}/settings")
def get_data_source_settings(data_source_id: int, request: Request, db: Session = Depends(get_db)):
    from app.services.ds_settings import serialize_ds_settings

    assert_data_source_access(request, db, data_source_id)
    ds = (
        db.query(DataSource)
        .options(joinedload(DataSource.store))
        .filter(DataSource.id == data_source_id)
        .first()
    )
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return serialize_ds_settings(ds)


@router.put("/data-sources/{data_source_id}/settings")
def update_data_source_settings(
    data_source_id: int,
    body: DataSourceSettingsIn,
    request: Request,
    db: Session = Depends(get_db),
):
    from app.services.ds_settings import save_ds_config, serialize_ds_settings
    from app.services.scheduler import refresh_schedules

    assert_data_source_access(request, db, data_source_id)
    ds = (
        db.query(DataSource)
        .options(joinedload(DataSource.store))
        .filter(DataSource.id == data_source_id)
        .first()
    )
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    save_ds_config(db, ds, body.model_dump(exclude_unset=True))
    refresh_schedules()
    return serialize_ds_settings(ds)


@router.get("/data-sources/{data_source_id}/config/export")
def export_data_source_config(
    data_source_id: int,
    request: Request,
    include_review_orders: bool = True,
    db: Session = Depends(get_db),
):
    from app.services.config_export import build_config_export, export_filename

    assert_data_source_access(request, db, data_source_id)
    ds = (
        db.query(DataSource)
        .options(joinedload(DataSource.store))
        .filter(DataSource.id == data_source_id)
        .first()
    )
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    bundle = build_config_export(db, ds, include_review_orders=include_review_orders)
    content = json.dumps(bundle, ensure_ascii=False, indent=2)
    filename = export_filename(ds)
    return Response(
        content=content.encode("utf-8"),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/data-sources/{data_source_id}/review-orders/template")
def download_review_template(data_source_id: int, request: Request, db: Session = Depends(get_db)):
    from app.services.review_import import build_review_template_bytes

    assert_data_source_access(request, db, data_source_id)
    content = build_review_template_bytes()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="review_orders_template.xlsx"'},
    )


@router.post("/data-sources/{data_source_id}/review-orders/import")
async def import_review_orders_api(
    data_source_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    from app.services.review_import import import_review_orders

    assert_data_source_access(request, db, data_source_id)
    ds = db.query(DataSource).filter(DataSource.id == data_source_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    content = await file.read()
    result = import_review_orders(db, ds, content, strict=True)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail="; ".join(result.get("errors", ["导入失败"])))
    return result


@router.get("/data-sources/{data_source_id}/review-logistics/template")
def download_review_logistics_template(data_source_id: int, request: Request, db: Session = Depends(get_db)):
    from app.services.review_import import build_review_logistics_template_bytes

    assert_data_source_access(request, db, data_source_id)
    content = build_review_logistics_template_bytes()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="review_logistics_template.xlsx"'},
    )


@router.post("/data-sources/{data_source_id}/review-logistics/import")
async def import_review_logistics_api(
    data_source_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    from app.services.review_import import import_review_logistics

    assert_data_source_access(request, db, data_source_id)
    ds = db.query(DataSource).filter(DataSource.id == data_source_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    content = await file.read()
    result = import_review_logistics(db, ds, content, strict=True)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail="; ".join(result.get("errors", ["导入失败"])))
    return result


@router.get("/data-sources/{data_source_id}/sample-orders/template")
def download_sample_template(data_source_id: int, request: Request, db: Session = Depends(get_db)):
    from app.services.sample_import import build_sample_template_bytes

    assert_data_source_access(request, db, data_source_id)
    content = build_sample_template_bytes()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="sample_orders_template.xlsx"'},
    )


@router.post("/data-sources/{data_source_id}/sample-orders/import")
async def import_sample_orders_api(
    data_source_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    from app.services.sample_import import import_sample_orders

    assert_data_source_access(request, db, data_source_id)
    ds = db.query(DataSource).filter(DataSource.id == data_source_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    content = await file.read()
    result = import_sample_orders(db, ds, content, strict=True)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail="; ".join(result.get("errors", ["导入失败"])))
    return result
