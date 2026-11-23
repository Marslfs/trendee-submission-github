# -*- coding: utf-8 -*-
"""A3：--llm-rerank 不再是死代码。

用假 client（不触网）验证 mode="llm" 真的走 LLM 分支并按模型给的顺序返回；
再验证「模型返回乱码」会带 warning 降级到启发式，而不是静默吞异常。
"""
import io
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loguru import logger
from src import rerank


def _hits(n=8):
    return [
        {"chunk_id": f"p{i:03d}-0", "page": i + 1, "section": f"节{i}",
         "text": f"内容{i} " * 40, "n_chars": 200, "score": 1.0 - i * 0.05}
        for i in range(n)
    ]


def _client(content):
    """构造一个 chat.completions.create 返回伪造响应的假 client。"""
    resp = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))])
    return types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=lambda **kwargs: resp)))


def _capture():
    sink = io.StringIO()
    hid = logger.add(sink, level="DEBUG")
    return sink, hid


def test_llm_rerank_uses_model_order(monkeypatch):
    hits = _hits(8)
    monkeypatch.setattr(rerank, "get_client", lambda: (_client("5,2,0"), "fake-model"))
    sink, hid = _capture()
    try:
        out = rerank.rerank("为什么中国出海品牌需要进行 GEO 优化", hits, mode="llm")
    finally:
        logger.remove(hid)
    # 严格按模型给的编号顺序返回（不是启发式的分数顺序）
    assert [h["chunk_id"] for h in out] == ["p005-0", "p002-0", "p000-0"]
    # 走 LLM 分支必须留下日志，不允许静默吞
    assert "LLM 重排生效" in sink.getvalue()
    # LLM 分支不写启发式的 rerank_score
    assert all("rerank_score" not in h for h in out)


def test_llm_rerank_garbage_degrades_with_warning(monkeypatch):
    hits = _hits(8)
    monkeypatch.setattr(rerank, "get_client",
                        lambda: (_client("模型不知道该输出什么！！！"), "fake-model"))
    sink, hid = _capture()
    try:
        out = rerank.rerank("为什么中国出海品牌需要进行 GEO 优化", hits, mode="llm")
    finally:
        logger.remove(hid)
    # 降级到启发式：结果非空且每块补上 rerank_score
    assert out and all("rerank_score" in h for h in out)
    logs = sink.getvalue()
    assert "无法解析出有效编号" in logs and "降级" in logs


def test_out_of_range_ids_are_dropped(monkeypatch):
    """模型给了越界编号时只保留合法项，不抛 IndexError。"""
    hits = _hits(6)
    monkeypatch.setattr(rerank, "get_client", lambda: (_client("1,99,3,2"), "fake-model"))
    sink, hid = _capture()
    try:
        out = rerank.rerank("主题", hits, mode="llm")
    finally:
        logger.remove(hid)
    assert [h["chunk_id"] for h in out] == ["p001-0", "p003-0", "p002-0"]
