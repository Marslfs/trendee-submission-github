# -*- coding: utf-8 -*-
"""T2-6 Rerank：启发式重排（20 → 6），不依赖任何模型。

三条打分规则（每条可解释）：
1) 标题命中：query 的实词出现在 section 标题里 → 强加分。
   标题是作者标注的主题，命中标题的块几乎必然相关。
2) 长度惩罚：过短块（<60 字）信息量不足（多为封面页/大数字块，
   如实测抓到的 p016 "02"），降权；超长块引用粒度差，轻微降权。
3) 位置奖励：BM25 排名靠前的块有先验相关性，给平滑加分避免抖动。

LLM 重排接口同样保留：rerank_llm() 在有 API Key 时可用（一次调用），
rerank(topic, hits, mode="heuristic"|"llm") 二选一。
"""
from __future__ import annotations

from .index import tokenize


def rerank_heuristic(topic: str, hits: list[dict], top_n: int = 6) -> list[dict]:
    q_tokens = set(tokenize(topic))
    for rank, h in enumerate(hits):
        s = h["score"] / (h["score"] + 1)          # 0~1 归一
        sec_tokens = set(tokenize(h["section"]))
        title_hit = len(q_tokens & sec_tokens) / max(len(q_tokens), 1)
        s += 0.6 * title_hit                        # 标题命中奖励
        n = h["n_chars"]
        if n < 60:
            s -= 0.5                                # 封面/碎片惩罚
        elif n > 400:
            s -= 0.1
        s += 0.05 * max(0, 10 - rank) / 10          # BM25 先验平滑
        h["rerank_score"] = round(s, 4)
    return sorted(hits, key=lambda h: -h["rerank_score"])[:top_n]


def rerank(topic: str, hits: list[dict], top_n: int = 6, mode: str = "heuristic") -> list[dict]:
    if mode == "llm":
        out = rerank_llm(topic, hits, top_n)
        if out is not None:
            return out
        # 无 Key 时静默降级：启发式不算"砍"，架构文档里写明
    return rerank_heuristic(topic, hits, top_n)


def rerank_llm(topic: str, hits: list[dict], top_n: int = 6) -> list[dict] | None:
    """LLM 重排：把候选块编号后让模型挑 top_n。需要 OPENAI_API_KEY，缺则 None。"""
    try:
        from .generate import get_client
        client, model = get_client()
    except RuntimeError:
        return None
    numbered = "\n".join(f"[{i}] ({h['chunk_id']}) {h['section']}: {h['text'][:120]}" for i, h in enumerate(hits))
    prompt = (
        f"主题：{topic}\n以下是候选资料片段（带编号），请选出与主题最相关的 {top_n} 个编号，"
        f"按相关度降序，只输出逗号分隔的编号，不要其他内容：\n{numbered}"
    )
    try:
        resp = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}], temperature=0, timeout=30)
        ids = [int(x) for x in "".join(c for c in resp.choices[0].message.content if c.isdigit() or c == ",").split(",") if x < len(hits)]
        return [hits[i] for i in dict.fromkeys(ids)][:top_n]
    except Exception:
        return None
