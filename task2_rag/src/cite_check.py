# -*- coding: utf-8 -*-
"""T2-11 引用校验：解析 [S1] 标记 → 校验在检索集合内 → 未命中即降级。

拦截两类问题（题面追问点："模型引用了不存在的页码，怎么拦？"）：
1) 编号越界：正文标了 [S7] 但只给了 6 个来源 → 删除该标记并告警。
2) 编号合法但内容不符：可选强校验——要求标记所在句与来源有词面重叠，
   不达标同样降级处理（默认开启，可关）。

返回 (clean_text, warnings)：warnings 供 demo/eval 展示，也是
"引用可信度"的量化证据。
"""
from __future__ import annotations

import re

from .index import tokenize

CITE_RE = re.compile(r"\[(S\d+)\]")
_SENT_SPLIT = re.compile(r"([。！？；，,.!?][”’」』)】]?)")  # 句末+次级标点都切，避免同句连坐
_OVERLAP_MIN = 0.15  # 句与被引来源的词面重叠下限（词袋近似，足够拦明显编造）


def check(text: str, sources: list[dict], strict: bool = True) -> tuple[str, list[str]]:
    warnings: list[str] = []
    n = len(sources)
    sid2src = {s["sid"]: s for s in sources}

    def _overlap_ok(sentence: str, src: dict) -> bool:
        st = set(tokenize(sentence))
        tt = set(tokenize(src["section"] + " " + src["text"]))
        if not st:
            return False
        return len(st & tt) / len(st) >= _OVERLAP_MIN

    def _process_segment(seg: str) -> str:
        """对单个句子做越界删除 + 词面校验。"""
        sids = [m.group(1) for m in CITE_RE.finditer(seg)]
        if not sids:
            return seg
        bad = [s for s in sids if s not in sid2src]
        if bad:
            warnings.append(f"越界引用 {bad}（仅有 S1..S{n}）→ 已删除该标记")
            seg = CITE_RE.sub("", seg)
            sids = [s for s in sids if s in sid2src]
        if strict and sids:
            sentence = CITE_RE.sub("", seg).strip()
            ok_sids = [s for s in sids if _overlap_ok(sentence, sid2src[s])]
            dropped = [s for s in sids if s not in ok_sids]
            if dropped:
                warnings.append(f"引用 {dropped} 与所在句词面重叠不足 → 已降级删除")
                seg = CITE_RE.sub("", seg)
        return seg

    # 句级处理：同一行可能混着真引用句与编造句，按句切分才能精准降级
    out_lines = []
    for line in text.splitlines():
        segs = _SENT_SPLIT.split(line)
        out_lines.append("".join(_process_segment(s) for s in segs if s != ""))

    clean = "\n".join(out_lines)
    clean = re.sub(r" {2,}", " ", clean)  # 清理删标记后的双空格
    return clean, warnings


if __name__ == "__main__":
    srcs = [
        {"sid": "S1", "page": 4, "section": "为什么选择LLM-原生GEO?", "text": "GEO 让品牌进入 AI 深度记忆，提升可见性"},
        {"sid": "S2", "page": 12, "section": "GEO时代到来：AI投毒乱象", "text": "AI 投毒扰乱生成式引擎结果，合规成为行业诉求"},
    ]
    demo = "出海品牌必须做 GEO [S1]，否则会被时代抛弃 [S9]。这一结论来自调研 [S1]。\n合规是底线 [S2]。"
    clean, warns = check(demo, srcs)
    print("原文:", demo)
    print("清洗:", clean)
    for w in warns:
        print("⚠", w)
