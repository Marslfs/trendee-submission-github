# -*- coding: utf-8 -*-
"""C1：14 主题闸门扫描 → 混淆矩阵（目标 0 误拒 / 0 误放）。

用法（在 task2_rag/ 下）：python scripts/scan_guard.py
只跑 retrieve → rerank → guard，不触网、不调 LLM。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.guard import COVERAGE_GATE, DEGRADE_GATE, SCORE_GATE, guard  # noqa: E402
from src.rerank import rerank  # noqa: E402
from src.retrieve import retrieve  # noqa: E402

TOPICS = [
    ("为什么中国出海品牌需要进行 GEO 优化", True),
    ("Trendee 的 LLM-原生 GEO 技术架构", True),
    ("AI 问答引擎的工作原理与 GEO 的关系", True),
    ("GEO 的合规性风险有哪些", True),
    ("品牌如何进入 AI 的推荐名单", True),
    ("如何防 AI 投毒", True),
    ("如何提升跨境电商的询盘转化", True),
    ("AI 搜索会不会取代 SEO", True),
    ("生成式引擎优化和传统 SEO 的区别", True),
    ("万悉科技的客户名单和融资历史", False),
    ("万悉科技有多少员工", False),
    ("今天上海天气怎么样", False),
    ("退款流程和售后电话", False),
    ("竞争对手的市场份额", False),
]


def main() -> int:
    print(f"# 闸门扫描（SCORE_GATE={SCORE_GATE} / DEGRADE_GATE={DEGRADE_GATE} / COVERAGE_GATE={COVERAGE_GATE}）\n")
    print("| 主题 | 应否 | hits | top1 | 覆盖率 | mode | 判定 |")
    print("|---|---|---|---|---|---|---|")
    fn = fp = 0
    ok_count = 0
    scan_data = []
    for topic, should in TOPICS:
        hits = rerank(topic, retrieve(topic))
        g = guard(topic, hits)
        top1 = hits[0].get("rerank_score", hits[0].get("score", 0)) if hits else 0.0
        scan_data.append((should, top1, g.coverage))
        allowed = g.mode in ("normal", "degrade")
        ok = allowed == should
        if should and not allowed:
            fn += 1
        if not should and allowed:
            fp += 1
        ok_count += int(ok)
        flag = "✅" if ok else ("❌ 误拒" if should else "❌ 误放")
        print(f"| {topic} | {'放' if should else '拒'} | {len(hits)} | {top1:.3f} "
              f"| {g.coverage:.0%} | {g.mode} | {flag} |")
    print(f"\n**合计：{len(TOPICS)} 主题，误拒 {fn} / 误放 {fp}，判对 {ok_count}/{len(TOPICS)}**")

    # 阈值扫描：把同一批实测数据套回「旧两态逻辑」（score>=0.35 且 cov>=单一阈值），
    # 说明为什么不能靠把 COVERAGE_GATE 下调到 0.40 来消除误拒。
    print("\n## 附：单一 COVERAGE_GATE 阈值扫描（旧两态逻辑，score gate 固定 0.35）\n")
    print("| COVERAGE_GATE | 应放主题放行 | 应拒主题误放 | 说明 |")
    print("|---|---|---|---|")
    for thr in (0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70, 0.80):
        allow = [(should, cov) for should, top1, cov in scan_data
                 if top1 >= SCORE_GATE and cov >= thr]
        tp = sum(1 for should, _ in allow if should)
        fpx = sum(1 for should, _ in allow if not should)
        note = "贴着 14 条调参，换语料即失效" if thr <= 0.40 else ""
        print(f"| {thr:.2f} | {tp}/9 | {fpx}/5 | {note} |")
    print("\n> 结论：降到 0.40 虽能消除误拒，但等于贴着这 14 条测试集调参；"
          "本系统改为三态，保留 0.60 正常档，把 [0.40, 0.60) 做成 degrade 降级档。")
    return 0 if (fn == 0 and fp == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
