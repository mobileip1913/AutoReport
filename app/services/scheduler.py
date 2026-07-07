"""店铺日报定时生成（APScheduler）。"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import DataSource
from app.services.ds_settings import get_ds_config
from app.services.report_engine import generate_report_for_data_source

logger = logging.getLogger("autoreport.scheduler")
TZ = ZoneInfo("Asia/Shanghai")

_scheduler: BackgroundScheduler | None = None


def _parse_hhmm(text: str) -> tuple[int, int] | None:
    text = (text or "").strip()
    if not text or ":" not in text:
        return None
    try:
        h, m = text.split(":", 1)
        hour, minute = int(h), int(m)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
    except ValueError:
        pass
    return None


def _yesterday_iso() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


def _run_scheduled_report(data_source_id: int):
    db: Session = SessionLocal()
    try:
        ds = db.query(DataSource).filter(DataSource.id == data_source_id).first()
        if not ds or not ds.config:
            return
        cfg = get_ds_config(ds)
        store_name = (cfg.get("meta") or {}).get("店铺名称") or ds.name
        report_date = _yesterday_iso()
        run = generate_report_for_data_source(
            db, ds.id, report_date, store_name, is_test=False
        )
        logger.info(
            "定时出报完成 ds=%s date=%s run_id=%s",
            ds.id, report_date, run.id,
        )
    except Exception:
        logger.exception("定时出报失败 ds=%s", data_source_id)
    finally:
        db.close()


def refresh_schedules():
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.remove_all_jobs()
    db = SessionLocal()
    try:
        for ds in db.query(DataSource).filter(DataSource.config.isnot(None)).all():
            cfg = get_ds_config(ds)
            parsed = _parse_hhmm(cfg.get("daily_generate_at") or "")
            if not parsed:
                continue
            hour, minute = parsed
            _scheduler.add_job(
                _run_scheduled_report,
                CronTrigger(hour=hour, minute=minute, timezone=TZ),
                args=[ds.id],
                id=f"daily_report_ds_{ds.id}",
                replace_existing=True,
            )
            logger.info("已注册定时出报 ds=%s at %02d:%02d", ds.id, hour, minute)
    finally:
        db.close()


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone=TZ)
    _scheduler.start()
    refresh_schedules()
    logger.info("APScheduler 已启动")


def shutdown_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
