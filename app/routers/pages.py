import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    DataImport,
    DataSource,
    FieldMapping,
    LogicalField,
    ReportRun,
    ReportTemplate,
    ReportValue,
    Store,
    TemplateLine,
    TemplateStatus,
)
from app.services.account_context import assert_data_source_access, page_context
from app.services.mapping_utils import part_rule_brief, part_rule_hints, build_field_labels_map
from app.services.report_engine import generate_report, generate_report_for_data_source
from app.services.schema import file_labels_from_meta, get_all_meta
from app.services.timezone import to_cst

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["cst"] = to_cst
templates.env.filters["part_rule_hints"] = part_rule_hints
templates.env.filters["part_rule_brief"] = part_rule_brief


def _render(name: str, request: Request, db: Session, **ctx):
    defaults = {
        "file_labels_by_ds": {},
        "field_labels_by_ds": {},
    }
    return templates.TemplateResponse(
        name,
        {"request": request, **defaults, **page_context(request, db), **ctx},
    )


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    return _render("dashboard.html", request, db)


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
    from app.services.mapping_utils import is_formula_line, is_manual_line, mapping_label, mapping_line_code, mapping_source_file_keywords, field_display_type
    from app.services.meichong_rules import PENDING_FILE_CODES

    from sqlalchemy.orm import joinedload

    ctx = page_context(request, db)
    current_store = ctx["current_store"]
    accessible_stores = ctx["accessible_stores"]
    if current_store and current_store.data_source:
        data_sources = [current_store.data_source]
    else:
        data_sources = list(ctx["accessible_data_sources"])
    if data_sources:
        ds_ids = [ds.id for ds in data_sources]
        data_sources = (
            db.query(DataSource)
            .options(joinedload(DataSource.store))
            .filter(DataSource.id.in_(ds_ids))
            .all()
        )
    store_by_ds_id = {s.data_source_id: s for s in accessible_stores if s.data_source_id}

    mappings = (
        db.query(FieldMapping)
        .filter(FieldMapping.data_source_id.in_([ds.id for ds in data_sources] or [0]))
        .order_by(FieldMapping.data_source_id, FieldMapping.sort_order, FieldMapping.id)
        .all()
    )
    fields = db.query(LogicalField).all()
    meta = get_all_meta(db, data_sources)
    file_labels_by_ds = file_labels_from_meta(meta)
    field_labels_by_ds = {
        ds.id: build_field_labels_map(
            [m for m in mappings if m.data_source_id == ds.id],
            fields,
        )
        for ds in data_sources
    }
    reuse_fields: dict[int, list[dict]] = {}
    for ds in data_sources:
        reuse_fields[ds.id] = [
            {
                "code": mapping_line_code(m),
                "name": mapping_label(m),
                "mapping_id": m.id,
                "configured": bool(m.parts or (m.sheet_name and m.column_header)),
                "source_files": mapping_source_file_keywords(m),
            }
            for m in mappings
            if m.data_source_id == ds.id and not is_formula_line(m) and not is_manual_line(m)
        ]

    grouped: dict[int, list[dict]] = {ds.id: [] for ds in data_sources}
    group_titles: dict[int, list[str]] = {ds.id: [] for ds in data_sources}
    auxiliary: dict[int, list[dict]] = {ds.id: [] for ds in data_sources}
    excel_config: dict[int, list[dict]] = {ds.id: [] for ds in data_sources}
    for m in mappings:
        item = {
            "mapping": m,
            "is_formula": is_formula_line(m),
            "is_manual": is_manual_line(m),
            "label": mapping_label(m),
            "line_code": mapping_line_code(m),
            "field_type": field_display_type(m, mapping_line_code(m)),
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

    from app.services.daily_report import build_dynamic_report_rows, list_excel_templates
    from app.services.ds_settings import serialize_ds_settings

    excel_templates = list_excel_templates()

    for ds in data_sources:
        ds_mappings = [m for m in mappings if m.data_source_id == ds.id]
        excel_config[ds.id] = build_dynamic_report_rows(
            ds_mappings,
            pending_file_codes=PENDING_FILE_CODES,
            label_fn=mapping_label,
            line_code_fn=mapping_line_code,
            is_manual_fn=is_manual_line,
            is_formula_fn=is_formula_line,
        )

    return _render(
        "mappings.html",
        request,
        db,
        mappings=mappings,
        grouped=grouped,
        group_titles=group_titles,
        auxiliary=auxiliary,
        excel_config=excel_config,
        fields=fields,
        data_sources=data_sources,
        accessible_stores=accessible_stores,
        store_by_ds_id=store_by_ds_id,
        excel_templates=excel_templates,
        modal_stores=accessible_stores,
        meta_json=json.dumps(meta, ensure_ascii=False),
        file_labels_by_ds=file_labels_by_ds,
        field_labels_by_ds=field_labels_by_ds,
        reuse_fields_json=json.dumps(reuse_fields, ensure_ascii=False),
        pending_file_codes=PENDING_FILE_CODES,
        ds_settings_json=json.dumps({
            ds.id: serialize_ds_settings(ds)
            for ds in data_sources
        }, ensure_ascii=False),
        ds_settings={ds.id: serialize_ds_settings(ds) for ds in data_sources},
    )


@router.get("/logs", response_class=HTMLResponse)
def list_logs(request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(url="/mappings", status_code=303)


@router.get("/reports", response_class=HTMLResponse)
def list_reports(request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(url="/daily", status_code=303)


@router.get("/reports/{run_id}", response_class=HTMLResponse)
def report_detail(run_id: int, request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(url=f"/daily?run_id={run_id}", status_code=303)


@router.get("/daily", response_class=HTMLResponse)
def daily_report_page(
    request: Request,
    run_id: int | None = None,
    db: Session = Depends(get_db),
):
    from app.services.daily_report import build_dynamic_report_rows, report_meta
    from app.services.ds_settings import serialize_ds_settings
    from app.services.mapping_utils import is_formula_line, is_manual_line, mapping_label, mapping_line_code, mapping_source_file_keywords, field_display_type, build_field_labels_map
    from app.services.meichong_rules import MEICHONG_TEMPLATE_NAME, PENDING_FILE_CODES
    from app.services.schema import get_all_meta

    ctx = page_context(request, db)
    current_store = ctx.get("current_store")
    accessible_stores = ctx.get("accessible_stores") or []
    store_by_ds_id = {
        s.data_source_id: s for s in accessible_stores if s.data_source_id
    }
    daily_sources = [ds for ds in ctx["accessible_data_sources"] if ds.config]

    template = (
        db.query(ReportTemplate).filter(ReportTemplate.name == MEICHONG_TEMPLATE_NAME).first()
    )

    run = None
    excel_rows = None
    meta = None
    active_ds_id = None
    meta_json = json.dumps(get_all_meta(db, daily_sources), ensure_ascii=False)
    reuse_fields_json = "{}"
    modal_data_sources = daily_sources
    modal_fields = db.query(LogicalField).all()

    if run_id:
        run = db.query(ReportRun).filter(ReportRun.id == run_id).first()

    if run:
        active_ds_id = run.data_source_id or _run_source_id(db, run)
    elif current_store and current_store.data_source_id:
        active_ds_id = current_store.data_source_id
    elif daily_sources:
        active_ds_id = daily_sources[0].id

    values = []
    mappings = []
    ds = None
    if active_ds_id:
        mappings = (
            db.query(FieldMapping)
            .filter(FieldMapping.data_source_id == active_ds_id)
            .all()
        )
        ds = db.query(DataSource).filter(DataSource.id == active_ds_id).first()
        if ds:
            modal_data_sources = [ds]
            meta_json = json.dumps(get_all_meta(db, [ds]), ensure_ascii=False)
            reuse_fields_json = json.dumps({
                ds.id: [
                    {
                        "code": mapping_line_code(m),
                        "name": mapping_label(m),
                        "mapping_id": m.id,
                        "configured": bool(m.parts or (m.sheet_name and m.column_header)),
                    }
                    for m in mappings
                    if not is_formula_line(m) and not is_manual_line(m)
                ]
            }, ensure_ascii=False)

    if run:
        values = (
            db.query(ReportValue)
            .filter(ReportValue.report_run_id == run.id)
            .order_by(ReportValue.sort_order)
            .all()
        )
        meta = report_meta(ds, run) if ds else None

    excel_rows = None
    if active_ds_id:
        excel_rows = build_dynamic_report_rows(
            mappings,
            values if run else None,
            pending_file_codes=PENDING_FILE_CODES,
            label_fn=mapping_label,
            line_code_fn=mapping_line_code,
            is_manual_fn=is_manual_line,
            is_formula_fn=is_formula_line,
        )

    ds_settings = {}
    file_labels_by_ds = {}
    if active_ds_id and ds:
        ds_settings = {ds.id: serialize_ds_settings(ds)}
        file_labels_by_ds = file_labels_from_meta(get_all_meta(db, [ds]))
    elif daily_sources:
        ds_settings = {d.id: serialize_ds_settings(d) for d in daily_sources}
        file_labels_by_ds = file_labels_from_meta(get_all_meta(db, daily_sources))

    field_labels_by_ds = {}
    if active_ds_id and mappings:
        field_labels_by_ds[active_ds_id] = build_field_labels_map(mappings, modal_fields)

    from datetime import date, timedelta

    default_report_date = (
        run.report_date if run
        else (date.today() - timedelta(days=1)).isoformat()
    )

    return _render(
        "daily.html",
        request,
        db,
        template=template,
        daily_sources=daily_sources,
        accessible_stores=accessible_stores,
        current_store=current_store,
        store_by_ds_id=store_by_ds_id,
        run=run,
        excel_rows=excel_rows,
        meta=meta,
        active_ds_id=active_ds_id,
        default_report_date=default_report_date,
        meta_json=meta_json,
        file_labels_by_ds=file_labels_by_ds,
        field_labels_by_ds=field_labels_by_ds,
        reuse_fields_json=reuse_fields_json,
        modal_data_sources=modal_data_sources,
        modal_fields=modal_fields,
        modal_stores=ctx.get("accessible_stores"),
        ds_settings=ds_settings,
        ds_settings_json=json.dumps(ds_settings, ensure_ascii=False),
        pending_file_codes=PENDING_FILE_CODES,
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
    request: Request,
    data_source_id: int = Form(...),
    report_date: str = Form(...),
    db: Session = Depends(get_db),
):
    assert_data_source_access(request, db, data_source_id)
    ds = db.query(DataSource).filter(DataSource.id == data_source_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    store_name = (ds.config or {}).get("meta", {}).get("店铺名称") or ds.name
    run = generate_report_for_data_source(db, ds.id, report_date, store_name, is_test=True)
    accept = (request.headers.get("accept") or "").lower()
    # fetch 提交时 Accept 含 application/json，返回可下载信息；普通表单仍走重定向
    wants_json = "application/json" in accept or request.query_params.get("format") == "json"
    if wants_json:
        return {
            "ok": True,
            "run_id": run.id,
            "report_date": run.report_date,
            "export_url": f"/daily/{run.id}/export",
            "redirect_url": f"/daily?run_id={run.id}",
        }
    return RedirectResponse(url=f"/daily?run_id={run.id}", status_code=303)


@router.get("/daily/review-template")
def daily_review_template(
    request: Request,
    data_source_id: int,
    db: Session = Depends(get_db),
):
    from app.services.review_import import build_review_template_bytes

    assert_data_source_access(request, db, data_source_id)
    content = build_review_template_bytes()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="review_orders_template.xlsx"'},
    )


@router.get("/daily/review-logistics-template")
def daily_review_logistics_template(
    request: Request,
    data_source_id: int,
    db: Session = Depends(get_db),
):
    from app.services.review_import import build_review_logistics_template_bytes

    assert_data_source_access(request, db, data_source_id)
    content = build_review_logistics_template_bytes()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="review_logistics_template.xlsx"'},
    )


@router.get("/daily/sample-template")
def daily_sample_template(
    request: Request,
    data_source_id: int,
    db: Session = Depends(get_db),
):
    from app.services.sample_import import build_sample_template_bytes

    assert_data_source_access(request, db, data_source_id)
    content = build_sample_template_bytes()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="sample_orders_template.xlsx"'},
    )


@router.get("/daily/export-sku")
def daily_export_sku_by_date(
    request: Request,
    data_source_id: int,
    report_date: str,
    db: Session = Depends(get_db),
):
    from app.services.sku_export import export_sku_excel

    assert_data_source_access(request, db, data_source_id)
    ds = db.query(DataSource).filter(DataSource.id == data_source_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    date_str = (report_date or "").strip()
    if not date_str:
        raise HTTPException(status_code=400, detail="请选择报表日期")

    store_name = (ds.config or {}).get("meta", {}).get("店铺名称") or ds.name
    path = export_sku_excel(db, ds, date_str, store_name)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
    )


@router.get("/daily/{run_id}/export-sku")
def daily_export_sku(run_id: int, request: Request, db: Session = Depends(get_db)):
    from app.services.sku_export import export_sku_for_run

    run = db.query(ReportRun).filter(ReportRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="报表不存在")
    ds_id = run.data_source_id or _run_source_id(db, run)
    ds = db.query(DataSource).filter(DataSource.id == ds_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="未找到报表对应的数据源")
    assert_data_source_access(request, db, ds.id)
    path = export_sku_for_run(db, run, ds)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
    )


@router.get("/daily/{run_id}/export")
def daily_export(run_id: int, db: Session = Depends(get_db)):
    from app.services.daily_report import export_daily_excel

    run = db.query(ReportRun).filter(ReportRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="报表不存在")
    ds = db.query(DataSource).filter(DataSource.id == _run_source_id(db, run)).first()
    if not ds:
        raise HTTPException(status_code=404, detail="未找到报表对应的数据源")
    from app.services.report_engine import sync_run_missing_values

    sync_run_missing_values(db, run, ds.id)
    values = (
        db.query(ReportValue)
        .filter(ReportValue.report_run_id == run_id)
        .order_by(ReportValue.sort_order)
        .all()
    )
    path = export_daily_excel(
        ds,
        run,
        values,
        mappings=db.query(FieldMapping).filter(FieldMapping.data_source_id == ds.id).all(),
    )
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
    )


@router.get("/imports")
def list_imports():
    """数据源由启动脚本自动注册，不再提供独立配置页。"""
    return RedirectResponse(url="/mappings", status_code=303)
