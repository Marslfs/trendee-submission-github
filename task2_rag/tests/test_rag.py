# -*- coding: utf-8 -*-
"""Task 2 核心链路测试：chunk 带页码 / 引用校验拦截假引用 / guard 拒答。"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cite_check import check
from src.chunk import split_page
from src.context import build_context
from src.guard import guard


def _page(page=7, title="测试标题", paras=None):
    return {"page": page, "title": title, "paras": paras or ["段落内容 " * 40], "sparse": False}


class TestChunk:
    def test_chunk_has_page_and_section(self):
        out = split_page(_page())
        assert out, "应产出至少一个 chunk"
        for c in out:
            assert c["page"] == 7
            assert c["section"] == "测试标题"
            assert c["chunk_id"].startswith("p007-")
            assert c["n_chars"] == len(c["text"])

    def test_no_source_fact_lost(self):
        """所有源段落文本都必须出现在某个 chunk 里（含 overlap 借段）。"""
        paras = [f"甲段第{i}句话，内容各异用于区分。" for i in range(20)]
        out = split_page(_page(paras=paras))
        joined = "".join(c["text"] for c in out)
        assert all(p in joined for p in paras)


class TestCiteCheck:
    SRC = [
        {"sid": "S1", "page": 4, "section": "为什么选择LLM-原生GEO?",
         "text": "GEO 让品牌进入 AI 深度记忆，提升在 AI 问答引擎中的可见性与推荐率"},
        {"sid": "S2", "page": 12, "section": "GEO时代到来：AI投毒乱象",
         "text": "AI 投毒指通过恶意内容操纵生成式引擎答案，合规成为 GEO 行业底线诉求"},
    ]

    def test_out_of_range_cite_removed(self):
        text = "品牌要做 GEO [S1]，另外一件编造的事 [S9]。\n合规很重要 [S2]。"
        clean, warns = check(text, self.SRC)
        assert "[S9]" not in clean
        assert "[S1]" in clean and "[S2]" in clean
        assert any("越界" in w for w in warns)

    def test_fake_content_cite_removed(self):
        """编号合法但句子与来源词面无关（编造内容）→ 降级删除。"""
        text = "Trendee 每年营收增长 300% [S1]。"
        clean, warns = check(text, self.SRC)
        assert "[S1]" not in clean
        assert any("重叠" in w for w in warns)

    def test_legit_cite_kept(self):
        text = "GEO 提升品牌在 AI 问答引擎中的可见性与推荐率 [S1]。"
        clean, _ = check(text, self.SRC)
        assert "[S1]" in clean


class TestContext:
    def test_sources_numbered_sequentially(self):
        hits = [{"chunk_id": f"p00{i}-0", "page": i, "section": f"节{i}", "text": f"内容{i}" * 10}
                for i in (1, 2, 3)]
        ctx, srcs = build_context(hits)
        assert [s["sid"] for s in srcs] == ["S1", "S2", "S3"]
        for s in srcs:
            assert f"[{s['sid']}] (page {s['page']}" in ctx

    def test_budget_sentence_cut(self):
        """超预算时按句子截断，不产生半个词。"""
        hits = [{"chunk_id": "p001-0", "page": 1, "section": "节",
                 "text": "句子。" * 2000}]
        ctx, _ = build_context(hits, budget=500)
        assert len(ctx) <= 600
        assert ctx.count("句子。") == ctx.rstrip().count("句子。")


class TestGuard:
    def test_off_corpus_topic_refused(self):
        """PDF 外主题（客户名单/融资）应拒答。"""
        hits = [{"chunk_id": "p003-0", "page": 3, "section": "万悉科技合规GEO技术获媒体广泛报道",
                 "text": "万悉科技获新华网、央广网报道，树立 GEO 合规技术标杆", "score": 2.0, "rerank_score": 1.0}]
        g = guard("万悉科技的客户名单和融资历史", hits)
        assert not g.allowed

    def test_in_corpus_topic_allowed(self):
        hits = [
            {"chunk_id": "p004-0", "page": 4, "section": "为什么选择LLM-原生GEO?",
             "text": "中国出海品牌通过 GEO 进入 AI 深度记忆，提升在生成式引擎中的可见性，"
                     "GEO 内容优化适配大语言模型与检索增强生成机制",
             "score": 2.0, "rerank_score": 1.2},
            {"chunk_id": "p014-0", "page": 14, "section": "GEO价值：品牌营销的AI统筹大脑",
             "text": "中国品牌通过 GEO 统一信息策略并优化内容输出，强化 AI 对品牌的深度记忆，"
                     "实现品牌资产的数字化长效沉淀",
             "score": 1.5, "rerank_score": 1.0},
        ]
        g = guard("为什么中国出海品牌需要进行 GEO 优化", hits)
        assert g.allowed


class TestOfflinePipeline:
    """端到端（离线模式）：全链路产物可保存、拒答路径可渲染。"""

    def test_pipeline_runs_without_key(self):
        r = subprocess.run(
            [sys.executable, "-m", "pipeline", "万悉科技的客户名单", "--no-save"],
            cwd=ROOT, capture_output=True, text=True, timeout=120, encoding="utf-8")
        assert r.returncode == 0
        assert "refused" in r.stdout and "true" in r.stdout
        assert "资料不足" in r.stdout

    def test_index_files_exist(self):
        assert (ROOT / "data" / "index" / "bm25.pkl").exists()
        chunks = (ROOT / "data" / "index" / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(chunks) >= 30
        rec = json.loads(chunks[0])
        assert {"chunk_id", "page", "section", "text"} <= set(rec)
