# -*- coding: utf-8 -*-
"""C4：fill_missing_dates=true 服务端补零；默认 false 保持旧快照不变。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
import src.api as api  # noqa: E402

PARAMS = {"start_date": "2024-01-20", "end_date": "2024-01-26", "platforms": "website"}


def _client(monkeypatch):
    monkeypatch.setattr(api, "DB_PATH", ROOT / "data" / "sales.duckdb")
    return TestClient(api.app)


def test_fill_missing_dates_returns_full_week(monkeypatch):
    r = _client(monkeypatch).get(
        "/api/v1/sales/trend", params={**PARAMS, "fill_missing_dates": "true"}).json()
    assert r["count"] == 7 and len(r["data"]) == 7
    assert r["meta"]["filled"] is True
    assert [d["date"] for d in r["data"]] == [
        "2024-01-20", "2024-01-21", "2024-01-22", "2024-01-23",
        "2024-01-24", "2024-01-25", "2024-01-26",
    ]
    zeros = [d for d in r["data"] if d["total_sales"] == 0]
    assert zeros and all(d["records"] == 0 and d["by_platform"] == {} for d in zeros)


def test_default_behavior_unchanged(monkeypatch):
    r = _client(monkeypatch).get("/api/v1/sales/trend", params=PARAMS).json()
    assert r["count"] == 4
    assert "filled" not in r["meta"]
