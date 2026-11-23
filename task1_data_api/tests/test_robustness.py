"""T1-G 鲁棒性回归：题面之外的写法（G1–G6）必须有可预测、可解释的判定。

样本来源：评审现场构造的 6 类对抗标题，固化在这里防止回归。
分组与判定依据（与 normalize.py 的 docstring 一致）：
  G1 书写变体：组合词 / 复数 / 斜杠 / 全角 / 全大写
  G2 拼写误差：maxi/dress 的 DL≤1 变体
  G3 属性词误杀：mini/midi 作为修饰语时不得当成长度档位
  G4 型号编号：数字/型号/前缀不得干扰词级判定
  G5 型号与 product_id 冲突：同商品矛盾标题必须可见（dim_product.tag_conflict）
  G6 语义边界：模糊表达进灰区或给出规则号，不沉默丢弃
"""
from __future__ import annotations

import duckdb
import pandas as pd
import pytest

from src.ingest import build_rows
from src.normalize import normalize_title, tag_product

# (类别, 标题, 期望档位, 期望规则)
CASES = [
    # G1 书写变体
    ("G1", "MaxiDress", "core", "R3"),
    ("G1", "Maxi Dresses", "core", "R3"),
    ("G1", "Maxi/Dress", "core", "R3"),
    ("G1", "ＭＡＸＩ　ＤＲＥＳＳ", "core", "R3"),
    ("G1", "MAXI-DRESS", "core", "R3"),
    # G2 拼写误差
    ("G2", "Maxy Dress", "core", "R3"),
    ("G2", "Maxi Dres", "core", "R3"),
    ("G2", "Maxi Dresss", "core", "R3"),
    # G3 属性词（最危险：误杀会把真实销量漏出趋势）
    ("G3", "Maxi Dress Midi Length", "core", "R3"),
    ("G3", "Maxi Dress Mini Print", "core", "R3"),
    ("G3", "Maxi Dress Petite", "core", "R3"),
    ("G3", "Midi Maxi Dress", "gray_zone", "R6"),   # 档位信号矛盾 → 灰区待人工确认
    # G4 型号 / 编号混入
    ("G4", "Model A12 Maxi Dress", "core", "R3"),
    ("G4", "Maxi Dress A-12", "core", "R3"),
    ("G4", "Maxi Dress No.2001", "core", "R3"),
    ("G4", "2001 Maxi Dress", "core", "R3"),
    ("G4", "SKU#4471 Maxi Dress", "core", "R3"),
    # G6 语义边界
    ("G6", "Maxi Length Dress", "core", "R3"),
    ("G6", "Long Gown Dress", "gray_zone", "R4"),
    ("G6", "Floor Length Dress", "gray_zone", "R4"),
    ("G6", "Maxi Dress Tea Length", "core", "R3"),
    # 负样本：不得回归（子串误伤 / 同形词）
    ("NEG", "Maxi Skirt", "excluded", "R2"),
    ("NEG", "Mini Dress", "excluded", "R1"),
    ("NEG", "Midi Dress", "excluded", "R1"),
    ("NEG", "T-shirt Dress", "excluded", "R5"),
    ("NEG", "Dress Shirt", "excluded", "R5"),
    ("NEG", "Maxim Dress", "excluded", "R5"),
    ("NEG", "Address Dress", "excluded", "R5"),
]


@pytest.mark.parametrize("group,title,want_status,want_rule", CASES,
                         ids=[f"{c[0]}-{c[1]}" for c in CASES])
def test_adversarial_title(group, title, want_status, want_rule):
    status, rule = tag_product(title)
    assert (status, rule) == (want_status, want_rule), f"{group} 判定漂移：{title}"


def test_pass_rate_at_least_85_percent():
    """评审口径：≥20 条对抗样本通过率 ≥85%（这里 28 条，全量通过）。"""
    ok = sum(1 for _, t, s, r in CASES if tag_product(t) == (s, r))
    assert ok / len(CASES) >= 0.85


def test_normalize_idempotent():
    for _, title, _, _ in CASES:
        once = normalize_title(title)
        assert normalize_title(once) == once


def test_sql_and_python_agree_on_adversarial_set():
    """SQL 版（02_dwd_tag.sql）必须与 Python 权威口径给出同样的 (档位, 规则)。

    这条测试把「两版可能悄悄分叉」变成 CI 里的硬约束：
    任何一侧改规则而另一侧没跟上，这里立刻红。
    """
    con = duckdb.connect()
    try:
        con.execute("CREATE TABLE ods_sales_seed (product_id INTEGER, title VARCHAR)")
        con.executemany(
            "INSERT INTO ods_sales_seed VALUES (?, ?)",
            [(i + 1, t) for i, (_, t, _, _) in enumerate(CASES)],
        )
        sql = (__import__("pathlib").Path(__file__).resolve().parents[1]
               / "sql" / "02_dwd_tag.sql").read_text(encoding="utf-8")
        rows = con.execute(sql).fetchall()
    finally:
        con.close()
    got = {pid: (status, rule) for pid, _tn, status, rule in rows}
    for i, (group, title, status, rule) in enumerate(CASES):
        assert got[i + 1] == (status, rule), f"SQL/Python 分叉：{group} {title} → {got[i + 1]}"


def _fact_frame(rows: list[tuple[int, str]]) -> pd.DataFrame:
    """构造 build_rows 需要的最小列集合（platform 由 read_seed 从 source 派生）。"""
    return pd.DataFrame(
        [
            {
                "product_id": pid,
                "title": title,
                "sales_count": 1,
                "category": "dress",
                "user_id": f"u{i}",
                "platform": "app",
                "timestamp": pd.Timestamp(f"2024-01-0{i % 9 + 1} 10:00:00"),
            }
            for i, (pid, title) in enumerate(rows)
        ]
    )


def test_conflicting_titles_are_detected_not_silently_dropped():
    """G5：同一 product_id 出现矛盾标题时，必须落 tag_conflict 并保留全部变体。"""
    _, products = build_rows(_fact_frame([
        (9001, "Maxi Dress Floral"),
        (9001, "Midi Dress Blue"),
    ]))
    row = products.iloc[0]
    assert bool(row["tag_conflict"]) is True
    assert "Maxi Dress Floral" in row["title_variants"]
    assert "Midi Dress Blue" in row["title_variants"]


def test_consistent_titles_are_not_flagged():
    _, products = build_rows(_fact_frame([
        (9002, "Maxi Dress Floral"),
        (9002, "MaxiDress Floral"),      # 同一档位的书写变体，不算冲突
    ]))
    assert bool(products.iloc[0]["tag_conflict"]) is False
