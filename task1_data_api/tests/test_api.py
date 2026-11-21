"""API 冒烟：先摄取到临时库，再用 TestClient 跑三个路由 + 错误分支。"""
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

import src.api as api
from src.ingest import ingest

ROOT = Path(__file__).resolve().parent.parent
TMP_DB = ROOT / "data" / "test_sales.duckdb"


def setup_module(module):
    TMP_DB.parent.mkdir(parents=True, exist_ok=True)
    if TMP_DB.exists():
        TMP_DB.unlink()
    ingest(ROOT.parent / "data_raw" / "样例销售数据.xlsx", TMP_DB)
    api.DB_PATH = TMP_DB
    module.client = TestClient(api.app)


def teardown_module(module):
    module.client.close()
    if TMP_DB.exists():
        TMP_DB.unlink()


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_trend_basic():
    r = client.get("/api/v1/sales/trend", params={
        "start_date": "2024-01-01", "end_date": "2024-03-13",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["count"] > 0
    assert body["data"][0]["date"] >= "2024-01-01"
    assert all("total_sales" in d for d in body["data"])


def test_trend_platform_filter():
    r = client.get("/api/v1/sales/trend", params={
        "start_date": "2024-01-01", "end_date": "2024-03-13", "platforms": "website",
    })
    body = r.json()
    for day in body["data"]:
        assert set(day["by_platform"].keys()) <= {"website"}


def test_trend_second_call_hits_cache():
    params = {"start_date": "2024-01-01", "end_date": "2024-01-31"}
    client.get("/api/v1/sales/trend", params=params)
    r2 = client.get("/api/v1/sales/trend", params=params)
    assert r2.json()["meta"]["cached"] is True


def test_bad_date_order_400():
    r = client.get("/api/v1/sales/trend", params={
        "start_date": "2024-03-01", "end_date": "2024-01-01",
    })
    assert r.status_code == 400


def test_unknown_platform_400():
    r = client.get("/api/v1/sales/trend", params={
        "start_date": "2024-01-01", "end_date": "2024-01-31", "platforms": "taobao",
    })
    assert r.status_code == 400


def test_missing_date_422():
    r = client.get("/api/v1/sales/trend")
    assert r.status_code == 422


def test_products_by_tag():
    r = client.get("/api/v1/products", params={"tag": "core"})
    assert r.status_code == 200
    assert all(p["tag_status"] == "core" for p in r.json()["data"])
