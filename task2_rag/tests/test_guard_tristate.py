# -*- coding: utf-8 -*-
"""C1：三态 guard + degrade 端到端（全程不触网、不调 LLM）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import src.generate as generate  # noqa: E402
from pipeline import run  # noqa: E402
from src.guard import COVERAGE_GATE, DEGRADE_GATE, SCORE_GATE, GuardResult  # noqa: E402


def _offline(monkeypatch):
    """让生成环节抛 RuntimeError，pipeline 走离线证据包，避免真实 API 调用。"""
    def _raise():
        raise RuntimeError("offline for test")
    monkeypatch.setattr(generate, "get_client", _raise)


def test_thresholds_and_result_fields():
    assert (SCORE_GATE, DEGRADE_GATE, COVERAGE_GATE) == (0.35, 0.40, 0.6)
    g = GuardResult(True, mode="degrade", coverage=0.5)
    assert g.allowed and g.mode == "degrade" and g.coverage == 0.5


def test_ai_search_vs_seo_degrades_with_notice(monkeypatch):
    _offline(monkeypatch)
    r = run("AI 搜索会不会取代 SEO")
    assert r["guard"]["mode"] == "degrade", r["guard"]
    assert DEGRADE_GATE <= r["guard"]["coverage"] < COVERAGE_GATE
    assert r["article"].startswith("> ⚠️ 资料覆盖度说明")
    assert len(r["article"]) > 200
    assert "未覆盖部分不作推断" in r["article"]


def test_client_list_still_refused(monkeypatch):
    _offline(monkeypatch)
    r = run("万悉科技的客户名单和融资历史")
    assert r.get("refused") is True
    assert r["guard"]["mode"] == "refuse"
    assert "资料不足" in r["article"]
