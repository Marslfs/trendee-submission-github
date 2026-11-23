# -*- coding: utf-8 -*-
"""重建 examples/*.json：用 TestClient 真实请求 API 并落盘（无需起 uvicorn）。

用法（在 task1_data_api/ 下）：python scripts/snap_examples.py
每次 API/DB 变更后重跑，保证快照与代码一致。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
import src.api as api  # noqa: E402

OUT = ROOT / "examples"
OUT.mkdir(exist_ok=True)
client = TestClient(api.app)

CASES = [
    ("trend-website.json", "/api/v1/sales/trend",
     {"start_date": "2024-01-20", "end_date": "2024-01-26", "platforms": "website"}),
    ("trend-gray-on.json", "/api/v1/sales/trend",
     {"start_date": "2024-01-20", "end_date": "2024-01-26", "include_gray_zone": "true"}),
    ("error-400.json", "/api/v1/sales/trend",
     {"start_date": "2024-02-01", "end_date": "2024-01-01"}),
    ("error-422.json", "/api/v1/sales/trend",
     {"start_date": "2024-01-01"}),
    ("products-core.json", "/api/v1/products", {"tag": "core"}),
    ("healthz.json", "/healthz", {}),
]

# C4：fill_missing_dates=true 的服务端补零快照（默认 false 不影响上面 6 条）
FILLED = ("trend-filled.json", "/api/v1/sales/trend",
          {"start_date": "2024-01-20", "end_date": "2024-01-26",
           "platforms": "website", "fill_missing_dates": "true"})


def main() -> None:
    cases = list(CASES)
    # 只有 API 支持该参数时才抓补零快照（C4 落地后自动生效）
    if "fill_missing_dates" in api.sales_trend.__code__.co_varnames:
        cases.append(FILLED)
    for name, path, params in cases:
        r = client.get(path, params=params)
        (OUT / name).write_text(
            json.dumps(r.json(), ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
        body = r.json()
        print(f"{name:26s} status={r.status_code} "
              f"count={body.get('count', '-')} data={len(body.get('data', []))}")


if __name__ == "__main__":
    main()
