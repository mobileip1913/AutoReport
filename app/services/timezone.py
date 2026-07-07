"""时区工具：数据库统一存 UTC，展示时转东八区（UTC+8 / 北京时间）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))


def to_cst(value: datetime | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """把 UTC（naive 或 aware）时间转换为东八区并格式化。None 返回空串。"""
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(CST).strftime(fmt)


def now_cst() -> datetime:
    """当前东八区时间（aware）。"""
    return datetime.now(CST)
