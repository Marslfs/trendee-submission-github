"""FastAPI：销售趋势查询服务（只读 DWS 层，不建 ADS）。

路由：
  GET /api/v1/sales/trend   日销量趋势（start/end/platforms/include_gray_zone/fill_missing_dates）→ 打 dws_sales_daily
  GET /api/v1/products      商品维表（按 tag 过滤）                        → 打 dim_product
  GET /healthz              存活 + DB 可用性探针                           → 打 dwd_fact_sales
错误处理：pydantic 校验 422；非法参数组合 400；结果空 200 + meta.count=0；
        DB 文件缺失 503（带修复提示）。
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from .cache import cache_stats, make_key, _cache

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "sales.duckdb"

app = FastAPI(
    title="Task1 Sales Trend API",
    version="1.0.0",
    description="maxi dress 日销量趋势查询（DuckDB + 预聚合 + TTL 缓存）",
)

VALID_PLATFORMS = {"website", "app", "marketplace"}
MAX_RANGE_DAYS = 366  # 上限防全表扫；生产分区下可放宽


def _connect() -> duckdb.DuckDBPyConnection:
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail=f"数据库不存在：{DB_PATH.name}。请先执行 python -m src.ingest 完成摄取。",
        )
    return duckdb.connect(str(DB_PATH), read_only=True)


def _validate_range(start: date, end: date, platforms: list[str]) -> None:
    if start > end:
        raise HTTPException(status_code=400, detail=f"start_date ({start}) 晚于 end_date ({end})")
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"日期范围超过 {MAX_RANGE_DAYS} 天上限")
    unknown = [p for p in platforms if p not in VALID_PLATFORMS]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"未知平台 {unknown}，可选值：{sorted(VALID_PLATFORMS)}",
        )


@app.get(
    "/api/v1/sales/trend",
    summary="maxi dress 日销量趋势",
    responses={
        400: {"description": "参数非法：日期倒序 / 区间超 366 天 / 未知平台"},
        503: {"description": "数据库未初始化（先跑 python -m src.ingest）"},
    },
)
def sales_trend(
    start_date: date = Query(..., description="起始日（含），Asia/Shanghai 口径"),
    end_date: date = Query(..., description="结束日（含）"),
    platforms: str = Query("", description="逗号分隔；空 = 全平台"),
    include_gray_zone: bool = Query(False, description="是否计入 gray_zone（long dress）"),
    fill_missing_dates: bool = Query(False, description="为 true 时补齐 start..end 每天（无数据补零），meta.filled=true；默认 false 保持旧快照行为"),
):
    platforms_list = [p.strip().lower() for p in platforms.split(",") if p.strip()]
    _validate_range(start_date, end_date, platforms_list)
    tags = ["core", "gray_zone"] if include_gray_zone else ["core"]

    key = make_key("trend", {
        "s": str(start_date), "e": str(end_date),
        "p": sorted(platforms_list), "g": include_gray_zone,
        "f": fill_missing_dates,
    })
    if key in _cache:
        hit = _cache[key]
        # 命中时 cache 统计需重取：否则返回的是首次构建时冻结的快照（entries 恒为 0）
        return {**hit, "meta": {**hit["meta"], "cached": True, "cache": cache_stats()}}

    con = _connect()
    try:
        sql = """
        SELECT a.dt_local,
               SUM(a.total_sales) AS total_sales,
               SUM(a.record_count) AS records,
               a.platform
        FROM dws_sales_daily a
        WHERE a.tag_status IN (?, ?)
          AND a.dt_local BETWEEN ? AND ?
        """
        params: list = [tags[0], tags[1] if len(tags) > 1 else "", start_date, end_date]
        if platforms_list:
            sql += " AND a.platform IN (" + ", ".join(["?"] * len(platforms_list)) + ")"
            params += platforms_list
        sql += " GROUP BY 1, 4 ORDER BY 1, 4"
        rows = con.execute(sql, params).fetchall()
        meta_row = con.execute(
            "SELECT COUNT(*), COALESCE(MIN(dt_local)::VARCHAR,''), COALESCE(MAX(dt_local)::VARCHAR,'') "
            "FROM dws_sales_daily WHERE tag_status IN (?, ?)",
            [tags[0], tags[1] if len(tags) > 1 else ""],
        ).fetchone()
    finally:
        con.close()

    by_date: dict[str, dict] = {}
    for dt, total, records, platform in rows:
        day = by_date.setdefault(str(dt), {"date": str(dt), "total_sales": 0, "records": 0, "by_platform": {}})
        day["total_sales"] += total
        day["records"] += records
        day["by_platform"][platform] = total

    # C4：可选服务端补零——把 start..end 的每一天都返回（无销售记录的日子补 0），
    # 避免前端自己按日期补零；默认 false 时保持旧快照行为。
    if fill_missing_dates:
        from datetime import timedelta
        cur = start_date
        while cur <= end_date:
            d = str(cur)
            if d not in by_date:
                by_date[d] = {"date": d, "total_sales": 0, "records": 0, "by_platform": {}}
            cur += timedelta(days=1)

    body = {
        "meta": {
            "start_date": str(start_date),
            "end_date": str(end_date),
            "platforms": platforms_list or sorted(VALID_PLATFORMS),
            "include_gray_zone": include_gray_zone,
            "agg_coverage": {"rows": meta_row[0], "min_date": meta_row[1], "max_date": meta_row[2]},
            "timezone": "Asia/Shanghai",
            "cached": False,
            "cache": cache_stats(),
        },
        "count": len(by_date),
        "data": sorted(by_date.values(), key=lambda d: d["date"]),
    }
    if fill_missing_dates:
        body["meta"]["filled"] = True
    _cache[key] = body
    return body


@app.get(
    "/api/v1/products",
    summary="商品维表（按 maxi dress 打标结果过滤）",
    responses={400: {"description": "非法 tag 取值"}, 503: {"description": "数据库未初始化"}},
)
def products(
    tag: str = Query("", description="core / gray_zone / excluded；空 = 全部"),
):
    tag = tag.strip().lower()
    if tag and tag not in {"core", "gray_zone", "excluded"}:
        raise HTTPException(status_code=400, detail=f"非法 tag={tag}，可选 core/gray_zone/excluded")
    con = _connect()
    try:
        if tag:
            rows = con.execute(
                "SELECT product_id, title_norm, category_raw, tag_status, tag_rule, is_gray_zone, "
                "title_variants, tag_conflict "
                "FROM dim_product WHERE tag_status = ? ORDER BY product_id", [tag]
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT product_id, title_norm, category_raw, tag_status, tag_rule, is_gray_zone, "
                "title_variants, tag_conflict "
                "FROM dim_product ORDER BY product_id"
            ).fetchall()
    finally:
        con.close()
    return {
        "count": len(rows),
        "data": [
            {"product_id": r[0], "title_norm": r[1], "category": r[2],
             "tag_status": r[3], "tag_rule": r[4], "is_gray_zone": r[5],
             "title_variants": r[6], "tag_conflict": r[7]}
            for r in rows
        ],
    }


@app.get("/healthz")
def healthz():
    try:
        con = _connect()
        n = con.execute("SELECT COUNT(*) FROM dwd_fact_sales").fetchone()[0]
        con.close()
        return {"status": "ok", "dwd_fact_sales_rows": n}
    except HTTPException as exc:
        return JSONResponse(status_code=503, content={"status": "down", "detail": exc.detail})
