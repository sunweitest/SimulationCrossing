"""时间工具：全站统一用北京时间（UTC+8）。

库里是 `timestamp without time zone`（见 models.py），所以一律写**不带时区的北京时间**，
读写对称、前端 `new Date("2026-11-03T12:00:00")` 会按本地时间解析，不会再有 8 小时偏差。
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

CN_TZ = ZoneInfo("Asia/Shanghai")


def now_cn() -> datetime:
    """当前北京时间（naive，用于写库）。"""
    return datetime.now(CN_TZ).replace(tzinfo=None)


def to_cn(dt: datetime | None) -> datetime | None:
    """把可能带时区的时间转成北京时间 naive。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(CN_TZ).replace(tzinfo=None)


def utc_now() -> datetime:
    """给 JWT 等需要 UTC 语义的场景用。"""
    return datetime.now(timezone.utc)
