# -*- coding: utf-8 -*-
"""T2-6 Rerank：启发式重排（20 → 6），不依赖任何模型。

三条打分规则（每条可解释）：
1) 标题命中：query 的实词出现在 section 标题里 → 强加分。
   标题是作者标注的主题，命中标题的块几乎必然相关。
2) 长度惩罚：过短块（<60 字）信息量不足（多为封面页/大数字块，
   如实测抓到的 p016 "02"），降权；超长块引用粒度差，轻微降权。
3) 位置奖励：BM25 排名靠前的块有先验相关性，给平滑加分避免抖动。

LLM 重排同样可用：rerank(topic, hits, mode="llm") 走 rerank_llm()。
缺 Key、解析失败、OpenAI SDK 异常都会 logger.warning 记录降级原因，
绝不静默吞异常。get_client 是模块级钩子，便于单测注入假 client（不触网）。
"""
from __future__ import annotations

from loguru import logger

from .index import tokenize


def get_client():
    """模块级可替换钩子：默认委托 generate.get_client（缺 Key 抛 RuntimeError）。

    单测 monkeypatch 本函数即可注入假 client，全程不触网。
    """
    from .generate import get_client as _real_get_client
    return _real_get_client()


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
        logger.warning("LLM 重排未产出结果，已降级为启发式重排（原因见上一条 warning）")
    return rerank_heuristic(topic, hits, top_n)


def rerank_llm(topic: str, hits: list[dict], top_n: int = 6) -> list[dict] | None:
    """LLM 重排：把候选块编号后让模型挑 top_n。

    返回 None 表示降级；所有降级路径都带 logger.warning 说明原因。
    只捕获「解析类异常 + OpenAI SDK 异常」，其余编程错误直接抛出，不静默吞。
    """
    try:
        client, model = get_client()
    except RuntimeError as e:
        logger.warning(f"LLM 重排不可用（{e}），降级启发式重排")
        return None

    numbered = "\n".join(
        f"[{i}] ({h['chunk_id']}) {h['section']}: {h['text'][:120]}"
        for i, h in enumerate(hits)
    )
    prompt = (
        f"主题：{topic}\n以下是候选资料片段（带编号），请选出与主题最相关的 {top_n} 个编号，"
        f"按相关度降序，只输出逗号分隔的编号，不要其他内容：\n{numbered}"
    )
    try:
        resp = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}],
            temperature=0, timeout=30)
        content = resp.choices[0].message.content or ""
        # 先转 int 再比较：原实现把 str 与 len(hits) 比大小，必然 TypeError 且被静默吞掉
        raw = "".join(ch for ch in content if ch.isdigit() or ch == ",")
        ids = [int(x) for x in raw.split(",")
               if x.strip().isdigit() and int(x) < len(hits)]
        ids = list(dict.fromkeys(ids))[:top_n]       # 去重且保序
        if not ids:
            logger.warning(f"LLM 重排返回内容无法解析出有效编号（原文：{content!r}），降级启发式重排")
            return None
        logger.info(f"LLM 重排生效：模型返回编号 {ids}，按该顺序取 {len(ids)} 个来源")
        return [hits[i] for i in ids]
    except (ValueError, IndexError, TypeError, AttributeError, KeyError) as e:
        logger.warning(f"LLM 重排结果解析失败（{type(e).__name__}: {e}），降级启发式重排")
        return None
    except Exception as e:
        # 只兜 OpenAI SDK 抛出的网络/限流/鉴权异常；其余编程错误不允许被吞
        if type(e).__module__.startswith("openai"):
            logger.warning(f"LLM 重排调用失败（{type(e).__name__}: {e}），降级启发式重排")
            return None
        raise
