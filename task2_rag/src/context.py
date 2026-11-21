# -*- coding: utf-8 -*-
"""T2-7 上下文构建：编号化片段 [S1..S6] + 页码 + 预算裁剪。

输出：
  context_text  # 拼进 prompt 的正文，每段以 [S1] (page 2) 开头
  sources       # 供 cite_check 回查与引用卡片展示

预算裁剪：超预算时按块从后往前丢，再对最后保留块做句子级截断
（切在句号/问号/分号后，绝不切词中间）。
"""
from __future__ import annotations

import re

CONTEXT_BUDGET = 3000  # 字符预算：40 块语料的 6 块，全文都塞得下，参数化是为可扩展

_SENT_END = re.compile(r"[。！？；.!?]")


def build_context(hits: list[dict], budget: int = CONTEXT_BUDGET) -> tuple[str, list[dict]]:
    sources, used = [], 0
    parts = []
    for i, h in enumerate(hits, 1):
        tag = f"[S{i}]"
        head = f"{tag} (page {h['page']} | {h['section']})\n"
        remain = budget - used - len(head)
        if remain <= 50:
            break
        text = h["text"]
        if len(text) > remain:
            # 句子级截断：在预算内找最后一个句末标点
            cut = 0
            for m in _SENT_END.finditer(text, 0, remain):
                cut = m.end()
            text = text[:cut] if cut > 50 else text[:remain]
        parts.append(f"{head}{text}")
        used += len(head) + len(text)
        sources.append({
            "sid": f"S{i}",
            "chunk_id": h["chunk_id"],
            "page": h["page"],
            "section": h["section"],
            "text": h["text"],
            "score": h.get("rerank_score", h.get("score")),
        })
    return "\n\n".join(parts), sources


if __name__ == "__main__":
    from .retrieve import retrieve
    from .rerank import rerank
    hits = rerank("为什么中国出海品牌需要进行 GEO 优化", retrieve("为什么中国出海品牌需要进行 GEO 优化"))
    ctx, srcs = build_context(hits)
    print(ctx[:800])
    print(f"\n... 共 {len(srcs)} 个来源, 上下文 {len(ctx)} 字符")
