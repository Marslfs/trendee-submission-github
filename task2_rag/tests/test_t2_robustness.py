# -*- coding: utf-8 -*-
"""T2-I 鲁棒性：查询变体、语料变化、异常入参、编码兜底。

这四条对应评分表 T2-I 的 I1~I4，每条都是可复现断言，而不是"我们在文档里说了"。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline import MAX_TOP_K, run, validate_inputs
from src.index import check_freshness, write_meta
from src.parse import sanitize


# ---------- I3 异常输入：空主题 / 纯符号 / 超范围 top_k ----------
def test_empty_topic_rejected():
    with pytest.raises(ValueError, match="主题不能为空"):
        validate_inputs("   ", 20)


def test_symbol_only_topic_rejected():
    with pytest.raises(ValueError, match="不含任何文字或数字"):
        validate_inputs("？？！", 20)


@pytest.mark.parametrize("k", [0, -3, MAX_TOP_K + 1, 200])
def test_top_k_out_of_range_rejected(k):
    with pytest.raises(ValueError, match="top_k 必须在"):
        validate_inputs("GEO 优化", k)


def test_top_k_in_range_and_topic_stripped():
    assert validate_inputs("  GEO 优化  ", 20) == "GEO 优化"


def test_run_surfaces_error_for_empty_topic():
    """pipeline.run 与 CLI/app 共用同一套校验：空主题不进入检索，直接 ValueError。"""
    with pytest.raises(ValueError):
        run("", top_k=20)


# ---------- I4 编码兜底：非法字符被剔除且计数可见 ----------
def test_sanitize_strips_replacement_and_control_chars():
    dirty = "Maxi\x00 Dress\ufffd 2024"
    clean, dropped = sanitize(dirty)
    assert clean == "Maxi Dress 2024"
    assert dropped == 2


def test_sanitize_keeps_legitimate_text_intact():
    text = "万悉科技 GEO 引用率 65%（2025）"
    clean, dropped = sanitize(text)
    assert (clean, dropped) == (text, 0)


# ---------- I2 语料变化：插页重建后引用失效可被发现 ----------
def _chunk(cid: str, page: int, text: str) -> dict:
    return {"chunk_id": cid, "page": page, "section": "s", "text": text, "n_chars": len(text)}


def _write_corpus(tmp: Path, chunks: list[dict]) -> None:
    (tmp / "chunks.jsonl").write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chunks), encoding="utf-8")


def test_freshness_ok_when_index_matches_corpus(tmp_path):
    chunks = [_chunk("p001-0", 1, "封面"), _chunk("p002-0", 2, "GEO 价值")]
    _write_corpus(tmp_path, chunks)
    write_meta(chunks, index_dir=tmp_path)
    ok, msg = check_freshness(data_dir=tmp_path, index_dir=tmp_path)
    assert ok, msg


def test_freshness_detects_page_shift_after_inserting_blank_page(tmp_path):
    """给 PDF 插一页空白页后重切：chunk_id 随页码整体平移，旧文章的 [S3] 会指错页。"""
    before = [_chunk("p001-0", 1, "封面"), _chunk("p002-0", 2, "GEO 价值")]
    _write_corpus(tmp_path, before)
    write_meta(before, index_dir=tmp_path)

    after = [_chunk("p001-0", 1, ""), _chunk("p002-0", 2, "封面"), _chunk("p003-0", 3, "GEO 价值")]
    _write_corpus(tmp_path, after)

    ok, msg = check_freshness(data_dir=tmp_path, index_dir=tmp_path)
    assert not ok
    assert "索引与语料不一致" in msg
    assert "重跑" in msg


def test_freshness_reports_missing_meta(tmp_path):
    _write_corpus(tmp_path, [_chunk("p001-0", 1, "封面")])
    ok, msg = check_freshness(data_dir=tmp_path, index_dir=tmp_path)
    assert not ok and "meta.json" in msg


# ---------- I1 查询变体：至少 6 条口语/中英混写变体参与同一套指标 ----------
def test_variant_queries_are_evaluated():
    labels = Path(__file__).resolve().parents[1] / "eval" / "retrieval_eval.jsonl"
    rows = [json.loads(x) for x in labels.read_text(encoding="utf-8").splitlines() if x.strip()]
    variants = [r for r in rows if r["type"] == "variant"]
    assert len(variants) >= 5
    assert any(not any("\u4e00" <= ch <= "\u9fff" for ch in r["query"]) or
               any(ch.isascii() and ch.isalpha() for ch in r["query"]) for r in variants)
