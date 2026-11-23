# -*- coding: utf-8 -*-
"""检索质量量化：recall@5 / MRR@10 / nDCG@10，三档配置对比。

为什么补这个脚本：此前"BM25 + 术语扩展 + 启发式 rerank"只有定性描述，
没有一条可复算的检索指标——评审无法判断"扩展/重排"到底有没有用。
本脚本把三档配置放在同一套人工标注上跑，差异就是这两步的净收益。

标注口径（诚实声明）：
- 36 条查询，标注单元是**页**（chunks 在本语料上是页级，见 README §2 的退化说明），
  由本人依据各页标题与正文首段判定「该页是否直接回答此问题」，二值相关。
- 单一标注者、无交叉校验；换标注者结论可能有 ±5% 波动。生产上应双人标注 + Kappa。
- V01~V06 是口语化/中英混写/无空格变体，单独统计（对应 T2-I 的 I1 查询变体）。

运行（在 task2_rag/ 下）：python scripts/eval_retrieval.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.index import tokenize                      # noqa: E402
from src.retrieve import load_index, retrieve, expand_query   # noqa: E402
from src.rerank import rerank_heuristic             # noqa: E402

LABELS = ROOT / "eval" / "retrieval_eval.jsonl"
OUT_MD = ROOT / "docs" / "retrieval_eval.md"
K_RECALL, K_NDCG = 5, 10


def load_labels() -> list[dict]:
    rows = [json.loads(x) for x in LABELS.read_text(encoding="utf-8").splitlines() if x.strip()]
    chunks = [json.loads(x) for x in (ROOT / "data" / "index" / "chunks.jsonl")
              .read_text(encoding="utf-8").splitlines()]
    by_page: dict[int, list[str]] = {}
    for c in chunks:
        by_page.setdefault(c["page"], []).append(c["chunk_id"])
    for r in rows:
        r["relevant"] = {cid for p in r["pages"] for cid in by_page.get(p, [])}
    return rows


def recall_at_k(ranked: list[str], rel: set[str], k: int) -> float:
    if not rel:
        return 0.0
    return len(set(ranked[:k]) & rel) / len(rel)


def mrr_at_k(ranked: list[str], rel: set[str], k: int = 10) -> float:
    for i, cid in enumerate(ranked[:k], 1):
        if cid in rel:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: list[str], rel: set[str], k: int = 10) -> float:
    dcg = sum(1.0 / math.log2(i + 1) for i, cid in enumerate(ranked[:k], 1) if cid in rel)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(rel), k) + 1))
    return dcg / ideal if ideal else 0.0


def run_configs(bm25, chunks, topic: str) -> dict[str, list[str]]:
    """三档配置各返回 top10 chunk_id 序列。"""
    # A. 原始 BM25：单一查询，不扩展、不重排
    scores = bm25.get_scores(tokenize(topic))
    raw = sorted(range(len(chunks)), key=lambda i: -scores[i])[:10]
    cfg_raw = [chunks[i]["chunk_id"] for i in raw]

    # B. BM25 + 术语扩展（多路归一融合）
    hits = retrieve(topic, top_k=20, bm25=bm25, chunks=chunks)
    cfg_exp = [h["chunk_id"] for h in hits[:10]]

    # C. 术语扩展 + 启发式 rerank（20 → 10）
    reranked = rerank_heuristic(topic, hits, top_n=10)
    cfg_rr = [h["chunk_id"] for h in reranked]

    return {"BM25 原始": cfg_raw, "BM25+术语扩展": cfg_exp, "+启发式 rerank": cfg_rr}


def summarize(rows: list[dict], configs: dict[str, dict[str, list[str]]]) -> dict[str, dict[str, float]]:
    out = {}
    for name in ("BM25 原始", "BM25+术语扩展", "+启发式 rerank"):
        r = sum(recall_at_k(configs[x["qid"]][name], x["relevant"], K_RECALL) for x in rows) / len(rows)
        m = sum(mrr_at_k(configs[x["qid"]][name], x["relevant"]) for x in rows) / len(rows)
        n = sum(ndcg_at_k(configs[x["qid"]][name], x["relevant"], K_NDCG) for x in rows) / len(rows)
        out[name] = {"recall@5": r, "mrr@10": m, "ndcg@10": n}
    return out


def main() -> int:
    rows = load_labels()
    bm25, chunks = load_index()
    configs = {x["qid"]: run_configs(bm25, chunks, x["query"]) for x in rows}

    topic_rows = [x for x in rows if x["type"] == "topic"]
    variant_rows = [x for x in rows if x["type"] == "variant"]
    all_sum = summarize(rows, configs)
    topic_sum = summarize(topic_rows, configs)
    variant_sum = summarize(variant_rows, configs)

    lines = ["# 检索质量实测（recall@5 / MRR@10 / nDCG@10）", "",
             "> 由 `scripts/eval_retrieval.py` 生成，标注文件 `eval/retrieval_eval.jsonl`。",
             f"> 查询 {len(rows)} 条（主题 {len(topic_rows)} + 口语/混写变体 {len(variant_rows)}），"
             "标注单元为页，二值相关。", ""]
    for title, s in (("全部查询", all_sum), ("主题类查询", topic_sum), ("口语/混写变体（T2-I I1）", variant_sum)):
        lines += [f"## {title}（n={len(rows) if title == '全部查询' else len(topic_rows) if '主题' in title else len(variant_rows)}）", "",
                  "| 配置 | recall@5 | MRR@10 | nDCG@10 |", "|---|---|---|---|"]
        for name, v in s.items():
            lines.append(f"| {name} | {v['recall@5']:.3f} | {v['mrr@10']:.3f} | {v['ndcg@10']:.3f} |")
        lines.append("")

    # 变体查询逐条：让"口语化是否仍能召回"可核对
    lines += ["## 口语/混写变体逐条（top5 命中情况）", "",
              "| qid | 查询 | top5 命中 | 相关数 |", "|---|---|---|---|"]
    for x in variant_rows:
        top5 = configs[x["qid"]]["+启发式 rerank"][:5]
        hit = len(set(top5) & x["relevant"])
        lines.append(f"| {x['qid']} | {x['query']} | {hit} | {len(x['relevant'])} |")
    lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"queries={len(rows)} (topic={len(topic_rows)}, variant={len(variant_rows)})")
    for title, s in (("ALL", all_sum), ("TOPIC", topic_sum), ("VARIANT", variant_sum)):
        print(f"\n[{title}]")
        for name, v in s.items():
            print(f"  {name:16s} recall@5={v['recall@5']:.3f}  MRR@10={v['mrr@10']:.3f}  nDCG@10={v['ndcg@10']:.3f}")
    print(f"\n[written] {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
