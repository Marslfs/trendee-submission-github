# -*- coding: utf-8 -*-
"""A5 / B4：tag_rule 可解释打标真实落库 + API 返回 + SQL 与 Python 逐商品一致。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import duckdb
from fastapi.testclient import TestClient

import src.api as api
from src.ingest import read_seed
from src.normalize import normalize_title, tag_product, tag_title


def test_tag_product_rule_ids():
    assert tag_product("maxi skirt") == ("excluded", "R2")
    assert tag_product("elegant long dress") == ("gray_zone", "R4")
    assert tag_product("maxi dress floral") == ("core", "R3")
    assert tag_product("summer mini dress") == ("excluded", "R1")
    assert tag_product("casual dress") == ("excluded", "R5")
    # 薄封装必须保持旧行为
    assert tag_title("maxi skirt") == "excluded"
    assert tag_title("maxi dress") == "core"


def test_api_returns_tag_rule(monkeypatch):
    monkeypatch.setattr(api, "DB_PATH", ROOT / "data" / "sales.duckdb")
    client = TestClient(api.app)
    r = client.get("/api/v1/products", params={"tag": "excluded"})
    assert r.status_code == 200
    rows = r.json()["data"]
    d = {p["product_id"]: p for p in rows}
    assert d[2027]["tag_rule"] == "R2"          # maxi skirt
    assert all("tag_rule" in p for p in rows)


def test_api_gray_zone_rule_and_counts(monkeypatch):
    monkeypatch.setattr(api, "DB_PATH", ROOT / "data" / "sales.duckdb")
    client = TestClient(api.app)
    g = client.get("/api/v1/products", params={"tag": "gray_zone"}).json()["data"]
    assert [(p["product_id"], p["tag_rule"]) for p in g] == [(2017, "R4")]
    assert client.get("/api/v1/products", params={"tag": "core"}).json()["count"] == 12
    assert client.get("/api/v1/products", params={"tag": "excluded"}).json()["count"] == 17


def test_sql_tag_matches_python_per_product():
    """B4：02_dwd_tag.sql（词级匹配）与 Python 版对 30 个商品结果完全一致。"""
    # 与 ingest.build_rows 的维表口径一致：按 timestamp 取每商品首个标题，
    # 得到 30 个商品（原始 xlsx 里同商品存在多个标题变体，DISTINCT 会有 33 行）。
    seed = (read_seed(ROOT.parent / "data_raw" / "样例销售数据.xlsx")
            .sort_values("timestamp")
            .groupby("product_id", as_index=False)
            .first()[["product_id", "title"]])
    py = {}
    for r in seed.itertuples(index=False):
        st, rule = tag_product(normalize_title(r.title))
        py[int(r.product_id)] = (st, rule)
    assert len(py) == 30

    con = duckdb.connect(":memory:")
    con.register("ods_sales_seed", seed)
    sql = (ROOT / "sql" / "02_dwd_tag.sql").read_text(encoding="utf-8")
    rows = con.execute(sql).fetchall()          # product_id, title_norm, tag_status, tag_rule
    con.close()
    assert len(rows) == 30
    for pid, tn, st_sql, rule_sql in rows:
        assert (st_sql, rule_sql) == py[int(pid)], (pid, tn, st_sql, rule_sql, py[int(pid)])
