from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import api, pages
from app.services.migrate import ensure_logical_fields, migrate_legacy_mappings, run_migrations
from app.services.meichong_rules import ensure_meichong_rules
from app.services.seed import ensure_meichong_datasource

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
        ensure_meichong_rules(db)
    finally:
        db.close()
