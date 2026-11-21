# -*- coding: utf-8 -*-
"""T2-11 幻觉控制：资料不足检测 → 明确拒答/声明缺口。

两层闸门（都在生成之前，省一次 API 调用，也是设计点）：
1) 检索得分闸门：top1 融合分低于阈值 → 整体拒答（话题与语料不相关，
   如"客户名单""融资历史"这类 PDF 外问题）。
2) 覆盖闸门：rerank 后可用来源 < 2 → 视为证据单薄，输出"资料不足"
   模板并声明缺口，不生成正文。

被拒时返回结构化结果而非异常，让上层（demo/CLI）统一渲染。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

SCORE_GATE = 0.35   # 融合分归一后 top1 下限（实测相关主题 top1 > 1.0，外主题 < 0.2）
MIN_SOURCES = 2     # 至少 2 个独立来源支撑一篇文章
COVERAGE_GATE = 0.6  # 主题实词覆盖率下限：专有名词命中分数可能虚高（如公司名），
                     # 真正的"资料不足"要看主题核心词是否真的出现在语料里
ENTITY_WORDS = {"万悉科技", "trendee"}  # 语料主体词，必然命中，不提供证据，排除统计


@dataclass
class GuardResult:
    allowed: bool
    reason: str = ""
    missing: list[str] = field(default_factory=list)


def _topic_coverage(topic: str, hits: list[dict]) -> float:
    """主题实词在 top-N 来源语料中的覆盖率。

    三个工程细节：
    - 排除 ENTITY_WORDS：公司名必然命中，对"客户名单"类问题无证据价值。
    - 中文词近似匹配：语料写"合规"、主题问"合规性"，按前 2 字匹配
      （中文双字词素是最小语义单元）；英文/数字仍用精确子串。
    - 主题里的停用词/单字过滤复用索引的分词与停用表。
    """
    from .index import tokenize, STOPWORDS
    STOP = set(STOPWORDS) | {"为什么", "需要", "进行", "如何", "什么", "哪些", "吗", "呢"}
    q_tokens = [t for t in tokenize(topic)
                if t not in STOP and t not in ENTITY_WORDS and len(t) >= 2]
    if not q_tokens:
        return 1.0
    corpus = " ".join(h["section"] + " " + h["text"] for h in hits[:8]).lower()
    corpus_tokens = set(tokenize(corpus))
    hit = 0
    for t in q_tokens:
        if t in corpus:
            hit += 1
            continue
        if re.match(r"[\u4e00-\u9fff]", t) and len(t) >= 2:
            prefix = t[:2]
            if any(w.startswith(prefix) or prefix == w[:2] for w in corpus_tokens if len(w) >= 2):
                hit += 1
    return hit / len(q_tokens)


def guard(topic: str, hits: list[dict]) -> GuardResult:
    if not hits:
        return GuardResult(False, "检索无任何命中：语料库为空或索引未构建", [topic])
    top = hits[0]
    score = top.get("rerank_score", top.get("score", 0))
    cov = _topic_coverage(topic, hits)
    if score < SCORE_GATE or cov < COVERAGE_GATE:
        return GuardResult(
            False,
            f"最相关片段得分 {score}、主题词覆盖率 {cov:.0%}（阈值 {SCORE_GATE} / {COVERAGE_GATE:.0%}）。"
            f"top 片段：p{top['page']}「{top['section']}」——判定主题超出 PDF 语料范围",
            [topic],
        )
    if len(hits) < MIN_SOURCES:
        return GuardResult(False, f"可用来源仅 {len(hits)} 个（< {MIN_SOURCES}），证据不足以支撑一篇完整文章",
                           [f"关于「{topic}」的更多资料"])
    return GuardResult(True)


def refusal_text(topic: str, g: GuardResult) -> str:
    lines = [
        f"# 资料不足，无法撰写「{topic}」",
        "",
        f"**原因**：{g.reason}",
        "",
        "本系统承诺仅使用品宣 PDF 内的事实（与 Trendee 反 AI 投毒、合规 GEO 的立场一致），",
        "因此对语料外主题选择明确拒答而非猜测。",
        "",
    ]
    if g.missing:
        lines.append("**缺口**：" + "；".join(g.missing))
    lines.append("")
    lines.append("建议：请更换为 PDF 覆盖范围内的主题，例如：")
    lines.append("- 为什么中国出海品牌需要进行 GEO 优化")
    lines.append("- Trendee 的 LLM-原生 GEO 技术架构")
    lines.append("- AI 问答引擎的工作原理与 GEO 的关系")
    return "\n".join(lines)


if __name__ == "__main__":
    from .retrieve import retrieve
    from .rerank import rerank
    for topic in ["为什么中国出海品牌需要进行 GEO 优化", "万悉科技的客户名单和融资历史"]:
        hits = rerank(topic, retrieve(topic))
        g = guard(topic, hits)
        print(f"『{topic}』allowed={g.allowed} | {g.reason[:60]}")
