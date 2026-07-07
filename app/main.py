from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import api, pages
from app.services.migrate import (
    ensure_logical_fields,
    migrate_cancelled_date_to_created,
    migrate_legacy_mappings,
    repair_actual_order_count_parts,
    run_migrations,
)
from app.services.meichong_rules import ensure_meichong_rules
from app.services.report_line_sync import backfill_mapping_line_codes, convert_formula_lines_to_fetch, sync_report_lines
from app.services.meichong_rules import TEMPLATE_GROUPS, TEMPLATE_LINES
from app.services.demo_accounts import ensure_demo_accounts
from app.services.seed import ensure_meichong_datasource
from app.services.scheduler import refresh_schedules, shutdown_scheduler, start_scheduler
from app.models import DataSource, FieldMapping

app = FastAPI(title="AutoReport Demo", description="跨境电商自动报表 Demo")

static_dir = Path("app/static")
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(pages.router)
app.include_router(api.router)


@app.on_event("startup")
def on_startup():
    data_dir = Path("./data")
    data_dir.mkdir(parents=True, exist_ok=True)
    run_migrations()
    db = SessionLocal()
    try:
        # 老 Demo 数据源（Amazon/Shopee/TikTok UK）已停用，仅保留美宠真实数据源
        ensure_meichong_datasource(db)
        ensure_logical_fields(db)
        migrate_legacy_mappings(db)
        migrate_cancelled_date_to_created(db)
        repair_actual_order_count_parts(db)
        ensure_meichong_rules(db)
        backfill_mapping_line_codes(db)
        for ds in db.query(DataSource).filter(DataSource.config.isnot(None)).all():
            if not db.query(FieldMapping).filter(
                FieldMapping.data_source_id == ds.id, FieldMapping.report_group.isnot(None)
            ).count():
                sync_report_lines(db, ds.id, TEMPLATE_LINES, TEMPLATE_GROUPS, only_missing=True)
        ensure_demo_accounts(db)
        for ds in db.query(DataSource).filter(DataSource.config.isnot(None)).all():
            convert_formula_lines_to_fetch(db, ds.id)
    finally:
        db.close()
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown():
    shutdown_scheduler()
