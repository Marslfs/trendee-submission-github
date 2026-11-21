"""时区口径：源数据 timestamp 声明为 UTC；业务聚合一律用 Asia/Shanghai 本地时间。

关键口径（实测摸底，写进质量报告）：
  300 条原始记录中 132 条 UTC >= 16:00，转 +8h 后落到次日——
  即「按日聚合」若不声明时区口径，趋势会整体右移。本表 dt_utc / dt_local 双列都保留。
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
CST = ZoneInfo("Asia/Shanghai")
TZ_NAME_UTC = "UTC"
TZ_NAME_LOCAL = "Asia/Shanghai"
OFFSET_HOURS = 8


def as_utc(naive: datetime) -> datetime:
    """把 naive timestamp 按声明口径挂上 UTC 时区。"""
    if naive.tzinfo is not None:
        return naive.astimezone(UTC)
    return naive.replace(tzinfo=UTC)


def to_local(dt_utc: datetime) -> datetime:
    """UTC → Asia/Shanghai（+8h，无夏令时）。"""
    return dt_utc.astimezone(CST)


def convert(naive: datetime) -> tuple[datetime, datetime]:
    """返回 (dt_utc, dt_local) 双列。"""
    u = as_utc(naive)
    return u, to_local(u)
