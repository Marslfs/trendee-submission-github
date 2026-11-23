# -*- coding: utf-8 -*-
"""C2：Task1 性能实测（EXPLAIN ANALYZE + P50/P95），不联网、不改交付库。

用法（task1_data_api/ 下）：python scripts/bench.py
从 data/sales.duckdb 合成放大到 30 万 / 300 万行，放大库一律写在系统临时目录，
绝不污染交付库 data/sales.duckdb。输出同时落 docs/bench_result.md。
"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "sales.duckdb"
OUT = ROOT / "docs" / "bench_result.md"

Q_DETAIL = ("SELECT CAST(dt_local AS DATE) AS d, SUM(sales_count) "
            "FROM fact GROUP BY 1 ORDER BY 1")
Q_DWS = "SELECT dt_local, SUM(total_sales) FROM dws GROUP BY 1 ORDER BY 1"
Q_PREFIX = ("SELECT CAST(dt_local AS DATE) AS d, SUM(sales_count) FROM fact "
            "WHERE CAST(dt_local AS DATE) BETWEEN DATE '2024-01-01' AND DATE '2024-01-31' "
            "GROUP BY 1 ORDER BY 1")


def build(n_target: int):
    tmp = Path(tempfile.gettempdir()) / f"bench_{n_target}.duckdb"
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    con.execute(f"ATTACH '{SRC.as_posix()}' AS src (READ_ONLY)")
    base = con.execute("SELECT COUNT(*) FROM src.dwd_fact_sales").fetchone()[0]
    k = max(1, n_target // base)
    con.execute(f"""
        CREATE TABLE fact AS
        SELECT f.product_id, f.platform, f.user_id, f.sales_count,
               f.dt_utc, f.dt_local, f.ingest_batch
        FROM src.dwd_fact_sales f CROSS JOIN generate_series(1, {k}) t(i)
    """)
    con.execute("CREATE TABLE dim_product AS SELECT * FROM src.dim_product")
    con.execute("""
        CREATE TABLE dws AS
        SELECT CAST(f.dt_local AS DATE) AS dt_local, f.platform, p.tag_status,
               SUM(f.sales_count) AS total_sales, COUNT(*) AS record_count
        FROM fact f JOIN dim_product p USING (product_id)
        WHERE p.tag_status IN ('core','gray_zone')
        GROUP BY 1, 2, 3
    """)
    actual = con.execute("SELECT COUNT(*) FROM fact").fetchone()[0]
    dws_rows = con.execute("SELECT COUNT(*) FROM dws").fetchone()[0]
    return con, tmp, actual, dws_rows


def bench(con, sql, n=20):
    con.execute(sql).fetchall()                      # warmup，排除首次编译开销
    ts = []
    for _ in range(n):
        t0 = time.perf_counter()
        con.execute(sql).fetchall()
        ts.append((time.perf_counter() - t0) * 1000)  # ms
    ts.sort()
    return ts[len(ts) // 2], ts[min(len(ts) - 1, int(len(ts) * 0.95))]


def explain(con, sql):
    """取 EXPLAIN ANALYZE 的关键行（总耗时 / 扫描行数 / 算子）。"""
    try:
        rows = con.execute("EXPLAIN ANALYZE " + sql).fetchall()
        # DuckDB 2.0.1 返回 2 列：('analyzed_plan', '<多行 box-drawing 计划文本>')，
        # 真正的计划在最后一列；把所有列拼起来再挑关键行。
        txt = "\n".join("\n".join(str(c) for c in row) for row in rows)
        # 去掉纯 box-drawing 边框行，保留全部有内容的行（含 Total Time / 扫描行数 / 算子）
        keep = []
        for ln in txt.splitlines():
            s = ln.strip(" │╭╮╰╯┒┎┚┖─")
            if s and s.strip():
                keep.append(s)
        # 只保留关键行：总耗时 / 扫描行数 / 算子名，避免 box-drawing 噪音
        key = [s for s in keep if any(k in s for k in
               ("Total Time", "Table Scan", "rows", "Function", "Filters",
                "Group By", "Summary", "Analyzed"))]
        return key[:14]
    except Exception as e:
        return [f"EXPLAIN ANALYZE 不可用: {type(e).__name__}: {e}"]


def main():
    lines = [
        "# Task1 性能实测（scripts/bench.py 自动生成）", "",
        "> 源库 `data/sales.duckdb`（288 行明细）；放大库写在系统临时目录，不污染交付库。",
        "> 每组查询 warmup 1 次后计时 20 次，单位 ms；EXPLAIN ANALYZE 取自 300 万行档。", "",
        "| 明细行数 | DWS 行数 | 明细 GROUP BY P50 / P95 (ms) | DWS 直查 P50 / P95 (ms) | 前缀过滤明细 P50 / P95 (ms) |",
        "|---|---|---|---|---|",
    ]
    explains: dict[str, list[str]] = {}
    for n in (288, 300_000, 3_000_000):
        con, tmp, actual, dws_rows = build(n)
        r1, r2, r3 = bench(con, Q_DETAIL), bench(con, Q_DWS), bench(con, Q_PREFIX)
        lines.append(f"| {actual:,} | {dws_rows} | {r1[0]:.2f} / {r1[1]:.2f} | "
                     f"{r2[0]:.2f} / {r2[1]:.2f} | {r3[0]:.2f} / {r3[1]:.2f} |")
        if n == 3_000_000:
            explains["detail"] = explain(con, Q_DETAIL)
            explains["dws"] = explain(con, Q_DWS)
        con.close()
        tmp.unlink(missing_ok=True)
    lines += ["", "## EXPLAIN ANALYZE 片段（300 万行）", "",
              "**明细 GROUP BY**：", "```text"] + explains.get("detail", []) + ["```", "",
              "**DWS 直查**：", "```text"] + explains.get("dws", []) + ["```"]
    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)
    print(f"[saved] {OUT}")


if __name__ == "__main__":
    main()
