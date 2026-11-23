# -*- coding: utf-8 -*-
"""T2-8 闸门控制：资料不足检测 → 三态输出（normal / degrade / refuse）。

判定顺序（都在生成之前，省一次 API 调用；逐层收窄）：
  ① 无命中                                        → refuse
  ② 分数闸门：top1 融合分 < SCORE_GATE=0.35      → refuse
  ③ 覆盖率闸门：主题实词覆盖率
       cov < DEGRADE_GATE=0.40                    → refuse（硬拒）
       0.40 <= cov < COVERAGE_GATE=0.60           → degrade（放行但降级声明）
       cov >= 0.60                                → 进入 ④
  ④ 来源数兜底：len(hits) < MIN_SOURCES=2         → refuse

真正拦住「客户名单/融资历史」的是第 ③ 层的主题实词覆盖率，不是分数，
也不是来源数：公司名在语料中高频出现会把融合分抬到 0.65 以上（> 0.35），
但主题核心词（客户/名单/融资/历史）覆盖率只有 33%，单靠分数闸门拦不住语料外主题。
COVERAGE_GATE=0.6 在 14 主题集上误拒 2/9，因此不调低阈值过拟合，
而把 [0.40, 0.60) 做成 degrade 档：既不编造，也不把有证据的主题硬拒
（混淆矩阵与阈值标定见 docs/eval.md）。

被拒时返回结构化结果而非异常，让上层（demo/CLI）统一渲染。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# 实测（14 主题，见 docs/eval.md）：语料外主题的分数并不低——客户名单 0.653、
# 员工数 0.750、退款 0.550、SEO 区别 0.641，都远超 0.35；语料内主题 0.64~1.30。
# 也就是「单靠分数闸门拦不住语料外主题」，必须靠主题实词覆盖率兜底。
SCORE_GATE = 0.35     # 融合分归一后 top1 下限（保留原值，不靠调阈值过拟合）
DEGRADE_GATE = 0.40   # 覆盖率硬拒线：低于此值判定超出语料范围
COVERAGE_GATE = 0.60  # 正常放行的覆盖率线；[DEGRADE_GATE, COVERAGE_GATE) 走 degrade
MIN_SOURCES = 2       # 至少 2 个独立来源支撑一篇文章
ENTITY_WORDS = {"万悉科技", "trendee"}  # 语料主体词，必然命中，不提供证据，排除统计


@dataclass
class GuardResult:
    allowed: bool                       # 兼容旧调用：normal / degrade 均为 True
    reason: str = ""
    missing: list[str] = field(default_factory=list)
    mode: str = "normal"                # normal | degrade | refuse
    coverage: float = 0.0               # 主题实词覆盖率，供上层声明与日志


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
    # ① 无命中
    if not hits:
        return GuardResult(
            False, mode="refuse", coverage=0.0,
            reason="检索无任何命中：语料库为空或索引未构建", missing=[topic],
        )
    top = hits[0]
    score = top.get("rerank_score", top.get("score", 0))
    cov = _topic_coverage(topic, hits)

    # ② 分数闸门 + ③ 覆盖率硬拒档
    if score < SCORE_GATE or cov < DEGRADE_GATE:
        return GuardResult(
            False, mode="refuse", coverage=cov,
            reason=f"最相关片段得分 {score}、主题词覆盖率 {cov:.0%}"
                   f"（硬拒阈值 {SCORE_GATE} / {DEGRADE_GATE:.0%}）。"
                   f"top 片段：p{top['page']}「{top['section']}」——判定主题超出 PDF 语料范围",
            missing=[topic],
        )
    # ④ 来源数兜底
    if len(hits) < MIN_SOURCES:
        return GuardResult(
            False, mode="refuse", coverage=cov,
            reason=f"可用来源仅 {len(hits)} 个（< {MIN_SOURCES}），证据不足以支撑一篇完整文章",
            missing=[f"关于「{topic}」的更多资料"],
        )
    # ③ 降级档：有证据但覆盖不完整，放行并显式声明，不硬拒
    if cov < COVERAGE_GATE:
        return GuardResult(
            True, mode="degrade", coverage=cov,
            reason=f"主题词覆盖率 {cov:.0%} ∈ [{DEGRADE_GATE:.0%}, {COVERAGE_GATE:.0%})："
                   f"放行但降级，文章开头须声明覆盖度",
        )
    return GuardResult(True, mode="normal", coverage=cov)


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
