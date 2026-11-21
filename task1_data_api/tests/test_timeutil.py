from datetime import datetime, timedelta

from src.timeutil import convert


def test_utc_to_cst_same_day():
    dt_utc, dt_local = convert(datetime(2024, 1, 1, 7, 0))
    assert dt_local.strftime("%Y-%m-%d %H:%M") == "2024-01-01 15:00"


def test_utc_to_cst_cross_day():
    # UTC 16:00 + 8h = 次日 00:00 —— 日聚合归属变化的关键边界
    dt_utc, dt_local = convert(datetime(2024, 1, 1, 16, 37))
    assert dt_local.strftime("%Y-%m-%d") == "2024-01-02"


def test_offset_is_plus_8():
    dt_utc, dt_local = convert(datetime(2024, 3, 13, 9, 45))
    # 比较钟面时间（去 tzinfo 后相减）：09:45 UTC → 17:45 CST
    assert (dt_local.replace(tzinfo=None) - dt_utc.replace(tzinfo=None)) == timedelta(hours=8)
