# -*- coding: utf-8 -*-
"""T2-2 清洗：去页眉页脚、合并断行、剔除纯图占位页。

输入 data/pages.jsonl → 输出 data/pages_clean.jsonl：
{
  "page": 1,
  "title": "...",
  "paras": ["段落1", "段落2", ...]   # 行 → 段落（断行合并、噪行剔除后）
}

三条规则（每条都可解释，面试能讲）：
1) 页眉页脚：出现在 >60% 页面首/尾 2 行位置的重复文本 → 全局剔除。
2) 断行合并：中文 PPT 断行无标点结尾，同一 block 相邻行直接拼接；
   遇到中英混排也不加空格（中文无需空格）。
3) 纯图占位页：清洗后正文 <10 字的页保留记录但标记 sparse=True，
   不进入 chunk（引言页/章节封面页常为纯图）。
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
IN, OUT = DATA / "pages.jsonl", DATA / "pages_clean.jsonl"

_HEAD_FOOT_HEAD_RATIO, _HEAD_FOOT_TAIL_RATIO = 0.6, 0.6
_MIN_PARA_CHARS = 10


def _merge_lines(lines: list[dict]) -> list[str]:
    """行 → 段落：相邻行拼接，直到出现"段落终结"特征。"""
    paras: list[str] = []
    buf = ""
    for l in lines:
        t = l["text"]
        if not buf:
            buf = t
            continue
        # 终结特征：buf 以中英标点/句号结尾，或当前行是明显新条目（中文顿号开头、
        # 短行带英文冒号结构）。PPT 行多为短语，保守合并即可，chunk 端还有截断兜底。
        if re.search(r"[。！？；：.]$", buf) and len(buf) >= 20:
            paras.append(buf)
            buf = t
        elif len(buf) + len(t) > 120:  # 单段保护上限
            paras.append(buf)
            buf = t
        else:
            buf += t
    if buf:
        paras.append(buf)
    return paras


def _group_by_block(lines: list[dict]) -> list[list[dict]]:
    groups: dict[int, list[dict]] = {}
    for l in lines:
        groups.setdefault(l.get("block", -1), []).append(l)
    return list(groups.values())


def _headfoot_pages(pages: list[dict]) -> tuple[set[str], set[str]]:
    """统计各页首/尾 2 行文本，出现率超过阈值的视为页眉/页脚。"""
    heads, tails = Counter(), Counter()
    for p in pages:
        ls = p["lines"]
        for l in ls[:2]:
            if len(l["text"]) <= 50:
                heads[l["text"]] += 1
        for l in ls[-2:]:
            if len(l["text"]) <= 50:
                tails[l["text"]] += 1
    n = len(pages)
    hset = {t for t, c in heads.items() if c / n >= _HEAD_FOOT_HEAD_RATIO}
    fset = {t for t, c in tails.items() if c / n >= _HEAD_FOOT_TAIL_RATIO}
    return hset, fset


def main() -> None:
    pages = [json.loads(x) for x in IN.read_text(encoding="utf-8").splitlines()]
    hset, fset = _headfoot_pages(pages)

    out, dropped_pages, dropped_lines = [], [], 0
    for p in pages:
        body = []
        n = len(p["lines"])
        for i, l in enumerate(p["lines"]):
            t = l["text"]
            # 页眉页脚判定：重复文本，或位于首/尾 2 行且与全局集合命中
            if t in hset or t in fset:
                dropped_lines += 1
                continue
            if (i < 2 or i >= n - 2) and len(t) <= 20 and not re.search(r"[。！？]", t):
                # 首/尾短行若在多页出现（宽松匹配，比如页码、英文角标）
                key = re.sub(r"\d+", "#", t)
                cnt = sum(1 for q in pages if any(re.sub(r"\d+", "#", x["text"]) == key for x in q["lines"][:2] + q["lines"][-2:]))
                if cnt / len(pages) >= _HEAD_FOOT_HEAD_RATIO:
                    dropped_lines += 1
                    continue
            body.append(l)
        # 按布局块分组独立成段：块=栏，跨块不拼接（防止左右栏内容串行）
        paras = []
        for blk in _group_by_block(body):
            paras.extend(x for x in _merge_lines(blk) if len(x) >= 2)
        total = sum(len(x) for x in paras)
        out.append({
            "page": p["page"],
            "title": p["title"],
            "paras": paras,
            "sparse": total < _MIN_PARA_CHARS,
        })
        if total < _MIN_PARA_CHARS:
            dropped_pages.append(p["page"])

    with OUT.open("w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"clean {len(pages)} pages -> {OUT.name}")
    print(f"  head lines removed by exact match: {sorted(hset)[:5]}")
    print(f"  foot lines removed by exact match: {sorted(fset)[:5]}")
    print(f"  sparse pages (skipped in chunking): {dropped_pages}")
    print(f"  per-page line drops: ~{dropped_lines}")


if __name__ == "__main__":
    main()
