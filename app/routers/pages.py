import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    DataImport,
    DataSource,
    FieldMapping,
    LogicalField,
    MappingLog,
    ReportRun,
    ReportTemplate,
    ReportValue,
    TemplateLine,
    TemplateStatus,
)
from app.services.report_engine import generate_report, generate_report_for_data_source
from app.services.schema import get_all_meta
from app.services.timezone import to_cst

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["cst"] = to_cst


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    templates_list = db.query(ReportTemplate).order_by(ReportTemplate.updated_at.desc()).all()
    recent_runs = db.query(ReportRun).order_by(ReportRun.created_at.desc()).limit(8).all()
    recent_logs = db.query(MappingLog).order_by(MappingLog.created_at.desc()).limit(6).all()
    data_sources = db.query(DataSource).all()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "templates_list": templates_list,
            "recent_runs": recent_runs,
            "recent_logs": recent_logs,
            "data_sources": data_sources,
        },
    )


@router.get("/templates", response_class=HTMLResponse)
def list_templates(request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(url="/mappings", status_code=303)


@router.get("/templates/{template_id}", response_class=HTMLResponse)
def template_detail(template_id: int, request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(url="/mappings", status_code=303)


@router.post("/templates/{template_id}/test")
def test_template(
    template_id: int,
    data_source_id: int = Form(...),
    report_date: str = Form(...),
    store_name: str = Form(...),
    db: Session = Depends(get_db),
):
    template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    generate_report(db, template, data_source_id, report_date, store_name, is_test=True)
    return RedirectResponse(url=f"/templates/{template_id}?tested=1", status_code=303)


@router.post("/templates/{template_id}/publish")
def publish_template(template_id: int, db: Session = Depends(get_db)):
    from datetime import datetime

    template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    template.status = TemplateStatus.PUBLISHED
    template.published_at = datetime.utcnow()
    template.version += 1
    db.commit()
    return RedirectResponse(url=f"/templates/{template_id}?published=1", status_code=303)


@router.post("/templates/{template_id}/unpublish")
def unpublish_template(template_id: int, db: Session = Depends(get_db)):
    template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    template.status = TemplateStatus.DRAFT
    db.commit()
    return RedirectResponse(url=f"/templates/{template_id}", status_code=303)


@router.get("/mappings", response_class=HTMLResponse)
def list_mappings(request: Request, db: Session = Depends(get_db)):
    from app.services.mapping_utils import is_formula_line, mapping_label, mapping_line_code

    mappings = (
        db.query(FieldMapping)
        .order_by(FieldMapping.data_source_id, FieldMapping.sort_order, FieldMapping.id)
        .all()
    )
    fields = db.query(LogicalField).all()
    data_sources = db.query(DataSource).all()
    meta = get_all_meta(db, data_sources)
    reuse_fields: dict[int, list[dict]] = {}
    for ds in data_sources:
        reuse_fields[ds.id] = [
            {"code": mapping_line_code(m), "name": mapping_label(m)}
            for m in mappings
            if m.data_source_id == ds.id and not is_formula_line(m)
        ]

    grouped: dict[int, list[dict]] = {ds.id: [] for ds in data_sources}
    group_titles: dict[int, list[str]] = {ds.id: [] for ds in data_sources}
    auxiliary: dict[int, list[dict]] = {ds.id: [] for ds in data_sources}
    for m in mappings:
        item = {
            "mapping": m,
            "is_formula": is_formula_line(m),
            "label": mapping_label(m),
            "line_code": mapping_line_code(m),
        }
        if (m.sort_order or 0) <= 0 and not m.report_group:
            auxiliary.setdefault(m.data_source_id, []).append(item)
            continue
        title = m.report_group or "未分组"
        bucket = grouped.setdefault(m.data_source_id, [])
        titles = group_titles.setdefault(m.data_source_id, [])
        if title not in titles:
            titles.append(title)
        item["group"] = title
        bucket.append(item)

    return templates.TemplateResponse(
        "mappings.html",
        {
            "request": request,
            "mappings": mappings,
            "grouped": grouped,
            "group_titles": group_titles,
            "auxiliary": auxiliary,
            "fields": fields,
            "data_sources": data_sources,
            "meta_json": json.dumps(meta, ensure_ascii=False),
            "reuse_fields_json": json.dumps(reuse_fields, ensure_ascii=False),
        },
    )


@router.get("/logs", response_class=HTMLResponse)
def list_logs(request: Request, db: Session = Depends(get_db)):
    logs = db.query(MappingLog).order_by(MappingLog.created_at.desc()).all()
    return templates.TemplateResponse(
        "logs.html",
        {"request": request, "logs": logs},
    )


@router.get("/reports", response_class=HTMLResponse)
def list_reports(request: Request, db: Session = Depends(get_db)):
    runs = db.query(ReportRun).order_by(ReportRun.created_at.desc()).all()
    return templates.TemplateResponse(
        "reports.html",
        {"request": request, "runs": runs},
    )


@router.get("/reports/{run_id}", response_class=HTMLResponse)
def report_detail(run_id: int, request: Request, db: Session = Depends(get_db)):
    run = db.query(ReportRun).filter(ReportRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="报表不存在")
    values = (
        db.query(ReportValue)
        .filter(ReportValue.report_run_id == run_id)
        .order_by(ReportValue.sort_order)
        .all()
    )
    return templates.TemplateResponse(
        "report_detail.html",
        {"request": request, "run": run, "values": values},
    )


@router.get("/daily", response_class=HTMLResponse)
def daily_report_page(
    request: Request,
    run_id: int | None = None,
    db: Session = Depends(get_db),
):
    from app.services.daily_report import build_grouped, report_meta
    from app.services.meichong_rules import MEICHONG_TEMPLATE_NAME

    template = (
        db.query(ReportTemplate).filter(ReportTemplate.name == MEICHONG_TEMPLATE_NAME).first()
    )
    daily_sources = [ds for ds in db.query(DataSource).all() if ds.config]

    run = None
    groups = None
    meta = None
    if run_id:
        run = db.query(ReportRun).filter(ReportRun.id == run_id).first()
        if run:
            values = (
                db.query(ReportValue)
                .filter(ReportValue.report_run_id == run_id)
                .order_by(ReportValue.sort_order)
                .all()
            )
            groups = build_grouped(values)
            ds = db.query(DataSource).filter(DataSource.id == _run_source_id(db, run)).first()
            meta = report_meta(ds, run) if ds else None

    return templates.TemplateResponse(
        "daily.html",
        {
            "request": request,
            "template": template,
            "daily_sources": daily_sources,
            "run": run,
            "groups": groups,
            "meta": meta,
        },
    )


def _run_source_id(db: Session, run) -> int:
    """推断报表对应的数据源：优先 run 记录，其次 config 店铺名，最后 legacy 导入表。"""
    if getattr(run, "data_source_id", None):
        return run.data_source_id

    for ds in db.query(DataSource).filter(DataSource.config.isnot(None)).all():
        store = (ds.config or {}).get("meta", {}).get("店铺名称")
        if store == run.store_name or ds.name == run.store_name:
            return ds.id

    imp = (
        db.query(DataImport)
        .filter(DataImport.store_name == run.store_name)
        .order_by(DataImport.created_at.desc())
        .first()
    )
    if imp:
        return imp.data_source_id

    first = db.query(DataSource).filter(DataSource.config.isnot(None)).first()
    return first.id if first else 0


@router.post("/daily/generate")
def daily_generate(
    data_source_id: int = Form(...),
    report_date: str = Form(...),
    db: Session = Depends(get_db),
):
    ds = db.query(DataSource).filter(DataSource.id == data_source_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    store_name = (ds.config or {}).get("meta", {}).get("店铺名称") or ds.name
    run = generate_report_for_data_source(db, ds.id, report_date, store_name, is_test=True)
    return RedirectResponse(url=f"/daily?run_id={run.id}", status_code=303)


@router.get("/daily/{run_id}/export")
def daily_export(run_id: int, db: Session = Depends(get_db)):
    from app.services.daily_report import export_daily_excel

    run = db.query(ReportRun).filter(ReportRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="报表不存在")
    values = (
        db.query(ReportValue)
        .filter(ReportValue.report_run_id == run_id)
        .order_by(ReportValue.sort_order)
        .all()
    )
    ds = db.query(DataSource).filter(DataSource.id == _run_source_id(db, run)).first()
    if not ds:
        raise HTTPException(status_code=404, detail="未找到报表对应的数据源")
    path = export_daily_excel(ds, run, values)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
    )


@router.get("/imports", response_class=HTMLResponse)
def list_imports(request: Request, db: Session = Depends(get_db)):
    from app.models import CatalogFile, EtlBatch

    data_sources = db.query(DataSource).all()
    etl_batches = db.query(EtlBatch).order_by(EtlBatch.created_at.desc()).limit(20).all()
    catalog_counts = {
        ds.id: db.query(CatalogFile).filter(CatalogFile.data_source_id == ds.id).count()
        for ds in data_sources
    }
    return templates.TemplateResponse(
        "imports.html",
        {
            "request": request,
            "data_sources": data_sources,
            "etl_batches": etl_batches,
            "catalog_counts": catalog_counts,
        },
    )
