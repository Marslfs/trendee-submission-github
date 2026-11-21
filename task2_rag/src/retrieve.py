# -*- coding: utf-8 -*-
"""T2-5 检索：BM25 + 查询扩展，top-k 召回。

查询扩展（Query Expansion）：主题句往往偏"营销语言"（如"为什么出海品牌
需要 GEO"），索引里是"产品语言"（"AI 问答引擎可见性"）。一个同义术语
映射表把主题翻译成 3~5 个子查询，分别打分后取各子查询 top 并集，
比单一查询召回稳。这是 BM25 路线上弥补语义召回缺口的手段——
等价于混合检索里的"另一路"，有 embedding 时可无缝替换。

输出：[(chunk_id, page, section, text, score), ...]
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path

from .index import tokenize

DATA = Path(__file__).resolve().parents[1] / "data"
INDEX_DIR = DATA / "index"

# 术语扩展表：主题语言 → 文档语言（品宣 PDF 实测用词）
EXPANSIONS = {
    "geo": ["GEO", "生成式引擎优化", "LLM 原生", "AI问答引擎", "可见性"],
    "出海": ["出海品牌", "全球化", "跨境", "中国品牌", "海外市场"],
    "优化": ["优化", "提升", "可见性", "内容策略"],
    "品牌": ["品牌", "品牌资产", "品宣", "深度记忆"],
    "ai": ["AI", "大模型", "AI问答引擎", "LLM"],
    "引用": ["引用率", "引用溯源", "被AI引用"],
    "合规": ["合规", "反投毒", "内容安全"],
    "流量": ["流量红利", "用户", "入口"],
    "生成式": ["生成式引擎", "AI问答", "大模型"],
    "内容": ["内容策略", "结构化", "内容生产"],
    "技术": ["技术", "架构", "知识图谱", "Embedding"],
    "效果": ["可量化", "指标", "引用率", "ROI"],
}


def expand_query(topic: str) -> list[str]:
    """主题 → 1 个原查询 + 命中映射表的扩展查询。"""
    qs = [topic]
    tl = topic.lower()
    for key, words in EXPANSIONS.items():
        if key in tl:
            qs.append(" ".join(words))
    return qs


def load_index() -> tuple:
    bm25 = pickle.loads((INDEX_DIR / "bm25.pkl").read_bytes())
    chunks = [json.loads(x) for x in (INDEX_DIR / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    return bm25, chunks


def retrieve(topic: str, top_k: int = 20, bm25=None, chunks=None) -> list[dict]:
    """多子查询并行打分，取每路 top 并集融合（简化 RRF：分数归一后求和）。"""
    if bm25 is None or chunks is None:
        bm25, chunks = load_index()

    max_s = 1e-9
    per_query_scores = []
    for q in expand_query(topic):
        s = bm25.get_scores(tokenize(q))
        mx = max(s) or 1.0
        per_query_scores.append(s)
        max_s = max(max_s, mx)

    fused = [0.0] * len(chunks)
    for s in per_query_scores:
        mx = max(s) or 1.0
        for i, v in enumerate(s):
            fused[i] += v / mx  # 每路归一化后求和：命中多路者胜出
    order = sorted(range(len(chunks)), key=lambda i: -fused[i])[:top_k]
    return [
        {**chunks[i], "score": round(fused[i], 4)}
        for i in order if fused[i] > 0
    ]


def main() -> None:
    for topic in ["为什么中国出海品牌需要进行 GEO 优化", "Trendee 的技术架构", "GEO 的合规性"]:
        hits = retrieve(topic, top_k=5)
        print(f"\n『{topic}』top{len(hits)}:")
        for h in hits:
            print(f"  [{h['chunk_id']} p{h['page']}] {h['section'][:20]} score={h['score']}")


if __name__ == "__main__":
    main()
