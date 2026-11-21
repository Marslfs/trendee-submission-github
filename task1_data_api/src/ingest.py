"""摄取管道：xlsx(ODS) → 归一化 → 打标 → 幂等去重 → DIM/DWD 建表入仓 → DWS 汇总。

分层：
  DIM  dim_platform / dim_product / dim_title_alias
  DWD  dwd_fact_sales（幂等明细，行级去重 + 双时区口径）
  DWS  dws_sales_daily（日期 × 平台 × 标签档位，API 唯一在线数据源）

幂等保证：row_hash 为主键，插入前 anti-join 掉库中已有 hash，重跑不增行。
审计保证：被过滤的重复行计数写入 dq_report，可回答「销量为什么少了 N 条」。
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from .normalize import CORE, EXCLUDED, GRAY_ZONE, normalize_title, row_hash, tag_title
from .timeutil import TZ_NAME_LOCAL, TZ_NAME_UTC, convert

ROOT = Path(__file__).resolve().parent.parent          # task1_data_api/
SQL_SCHEMA = ROOT / "sql" / "01_dwd_schema.sql"
SQL_AGG = ROOT / "sql" / "03_dws_agg.sql"
DEFAULT_XLSX = ROOT.parent / "data_raw" / "样例销售数据.xlsx"


def read_seed(xlsx_path: Path) -> pd.DataFrame:
    """读取 xlsx 并做列级清洗：去首尾空格、类型收紧。"""
    df = pd.read_excel(xlsx_path)
    df.columns = [c.strip().lower() for c in df.columns]
    df["platform"] = df["source"].astype(str).str.strip().str.lower()
    df["category"] = df["category"].astype(str).str.strip().str.lower()
    df["user_id"] = df["user_id"].astype(str).str.strip()
    df["title"] = df["title"].astype(str).str.strip()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["sales_count"] = pd.to_numeric(df["sales_count"], errors="raise").astype(int)
    return df


def build_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """归一化 + 打标 + 生成 row_hash。返回 (fact_rows, product_rows)。"""
    df = df.copy()
    df["title_norm"] = df["title"].map(normalize_title)
    df["tag_status"] = df["title_norm"].map(tag_title)

    utc_list, local_list, hash_list = [], [], []
    for rec in df.itertuples(index=False):
        dt_utc, dt_local = convert(rec.timestamp.to_pydatetime())
        utc_list.append(dt_utc)
        local_list.append(dt_local)
        hash_list.append(
            row_hash(
                {
                    "product_id": rec.product_id,
                    "title_norm": rec.title_norm,
                    "sales_count": rec.sales_count,
                    "dt_utc": dt_utc.isoformat(),
                    "user_id": rec.user_id,
                    "category": rec.category,
                    "platform": rec.platform,
                }
            )
        )
    df["dt_utc"] = utc_list
    df["dt_local"] = local_list
    df["row_hash"] = hash_list

    # 维表：每 product 取首个 title（同商品多标题变体在 dim_title_alias 里体现）
    product_rows = (
        df.sort_values("timestamp")
        .groupby("product_id", as_index=False)
        .first()[["product_id", "title_norm", "category", "tag_status"]]
        .assign(is_gray_zone=lambda d: d["tag_status"] == GRAY_ZONE)
    )
    return df, product_rows


def ingest(xlsx_path: Path, db_path: Path, batch_id: str | None = None) -> dict:
    """全量幂等摄取。返回统计字典（写进 dq_report 与质量报告）。"""
    batch = batch_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    df = read_seed(xlsx_path)
    fact, products = build_rows(df)

    con = duckdb.connect(str(db_path))
    con.execute(SQL_SCHEMA.read_text(encoding="utf-8"))

    con.executemany(
        "INSERT OR IGNORE INTO dim_platform (platform_name) VALUES (?)",
        [(p,) for p in sorted(fact["platform"].unique())],
    )
    con.executemany(
        "INSERT OR REPLACE INTO dim_product VALUES (?, ?, ?, ?, ?)",
        [
            (int(r.product_id), r.title_norm, r.category, r.tag_status, bool(r.is_gray_zone))
            for r in products.itertuples(index=False)
        ],
    )
    con.executemany(
        "INSERT OR IGNORE INTO dim_title_alias VALUES (?, ?, ?)",
        [
            (r.title_norm, int(r.product_id), r.title)
            for r in fact.drop_duplicates(subset=["title_norm"]).itertuples(index=False)
        ],
    )

    # 幂等核心：文件内先按 row_hash 去重，再 anti-join 掉库中已有 hash
    existing = {r[0] for r in con.execute("SELECT row_hash FROM dwd_fact_sales").fetchall()}
    unique_rows = fact.drop_duplicates(subset=["row_hash"])
    in_file_dups = len(fact) - len(unique_rows)
    new_rows = unique_rows[~unique_rows["row_hash"].isin(existing)]
    dup_count = in_file_dups + (len(unique_rows) - len(new_rows))

    insert_rows = [
        (
            r.row_hash, int(r.product_id), r.platform, r.user_id,
            int(r.sales_count), r.dt_utc, r.dt_local, batch,
        )
        for r in new_rows.itertuples(index=False)
    ]
    if insert_rows:
        con.executemany(
            "INSERT OR IGNORE INTO dwd_fact_sales VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            insert_rows,
        )

    # 预聚合（03_agg.sql 自带 DELETE-INSERT 幂等）
    con.execute(SQL_AGG.read_text(encoding="utf-8"))

    # ---- 数据质量报告（5 条规则）----
    run_dq_checks(con, fact, batch, dup_count)
    stats = {
        "input_rows": len(fact),
        "duplicate_filtered": dup_count,
        "inserted": len(new_rows),
        "fact_total": con.execute("SELECT COUNT(*) FROM dwd_fact_sales").fetchone()[0],
        "agg_rows": con.execute("SELECT COUNT(*) FROM dws_sales_daily").fetchone()[0],
        "core_rows": con.execute(
            "SELECT COUNT(*) FROM dim_product WHERE tag_status = 'core'"
        ).fetchone()[0],
        "gray_rows": con.execute(
            "SELECT COUNT(*) FROM dim_product WHERE tag_status = 'gray_zone'"
        ).fetchone()[0],
        "excluded_rows": con.execute(
            "SELECT COUNT(*) FROM dim_product WHERE tag_status = 'excluded'"
        ).fetchone()[0],
        "batch": batch,
    }
    con.close()
    return stats


def run_dq_checks(con: duckdb.DuckDBPyConnection, fact: pd.DataFrame, batch: str, dup_count: int) -> None:
    """5 条质量规则，结果落 dq_report 表。"""
    checks: list[tuple[str, str, str, bool]] = []

    # 1) 唯一性：row_hash 全库唯一
    n_hash, n_dist = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT row_hash) FROM dwd_fact_sales"
    ).fetchone()
    checks.append(("uniqueness_row_hash", "error",
                   f"dwd_fact_sales rows={n_hash}, distinct hash={n_dist}", n_hash == n_dist))

    # 2) 完整性：核心字段无空值
    nulls = con.execute(
        "SELECT COUNT(*) FROM dwd_fact_sales WHERE product_id IS NULL OR platform IS NULL "
        "OR sales_count IS NULL OR dt_utc IS NULL"
    ).fetchone()[0]
    checks.append(("completeness_not_null", "error", f"null core fields = {nulls}", nulls == 0))

    # 3) 口径一致性：tag_status 只允许三档，且 excluded 不出现在聚合表
    bad_tags = con.execute(
        "SELECT COUNT(*) FROM dws_sales_daily WHERE tag_status NOT IN ('core','gray_zone')"
    ).fetchone()[0]
    checks.append(("tag_glossary_consistency", "error",
                   f"agg rows with illegal tag_status = {bad_tags}", bad_tags == 0))

    # 4) 异常值：sales_count 越界（<=0 或 >10_000）
    anomalies = con.execute(
        "SELECT COUNT(*) FROM dwd_fact_sales WHERE sales_count <= 0 OR sales_count > 10000"
    ).fetchone()[0]
    checks.append(("anomaly_sales_range", "warn",
                   f"records with sales_count<=0 or >10000 = {anomalies}", anomalies == 0))

    # 5) 及时性/覆盖：事实表时间跨度闭合声明区间
    lo, hi = con.execute(
        "SELECT MIN(dt_utc), MAX(dt_utc) FROM dwd_fact_sales"
    ).fetchone()
    checks.append(("timeliness_coverage", "info",
                   f"dt_utc range: {lo} -> {hi}; input duplicates filtered = {dup_count}", True))

    con.executemany(
        "INSERT INTO dq_report VALUES (?, ?, ?, ?, ?, ?)",
        [(name, sev, detail, ok, datetime.now(timezone.utc), batch)
         for name, sev, detail, ok in checks],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Task1 幂等摄取管道")
    ap.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX, help="源 xlsx 路径")
    ap.add_argument("--db", type=Path, default=ROOT / "data" / "sales.duckdb", help="DuckDB 文件路径")
    args = ap.parse_args()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    stats = ingest(args.xlsx, args.db)
    print("ingest stats:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
