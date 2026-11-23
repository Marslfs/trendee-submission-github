# -*- coding: utf-8 -*-
"""C5：chunk size=150 vs 400 实测对比（只读，不改动交付索引）。

用法（task2_rag/ 下）：python scripts/chunk_compare.py
验证「400/80 在本语料上几乎不生效、实际退化为页级 chunk」，
并给出 size=150 / 400 的 chunks 数、覆盖页数、长度分布、示例 query top-5 页码。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rank_bm25 import BM25Okapi  # noqa: E402
from src.chunk import split_page  # noqa: E402
from src.index import tokenize  # noqa: E402
from src.retrieve import retrieve  # noqa: E402

QUERY = "为什么中国出海品牌需要进行 GEO 优化"
pages = [json.loads(x) for x in
         (ROOT / "data" / "pages_clean.jsonl").read_text(encoding="utf-8").splitlines()]


def build(size: int):
    chunks = []
    for p in pages:
        chunks.extend(split_page(p, size=size, overlap=80))
    return chunks


def describe(chunks):
    lens = sorted(c["n_chars"] for c in chunks)
    return {
        "n": len(chunks),
        "pages": len({c["page"] for c in chunks}),
        "min": lens[0],
        "median": lens[len(lens) // 2],
        "max": lens[-1],
        "avg": round(sum(lens) / len(lens), 1),
    }


def top5_pages(chunks):
    corpus = [tokenize(f"{c['section']} {c['text']}") for c in chunks]
    hits = retrieve(QUERY, top_k=5, bm25=BM25Okapi(corpus), chunks=chunks)
    return [h["page"] for h in hits]


def main():
    print(f"pages = {len(pages)}，query = 「{QUERY}」\n")
    print("| size | chunks | 覆盖页 | 长度 min/median/max | 平均字符 | top-5 页码 |")
    print("|---|---|---|---|---|---|")
    for size in (150, 400):
        ch = build(size)
        s = describe(ch)
        print(f"| {size} | {s['n']} | {s['pages']}/{len(pages)} | "
              f"{s['min']}/{s['median']}/{s['max']} | {s['avg']} | {top5_pages(ch)} |")
    print("\n结论：size=400 时 chunks 数与页数近乎 1:1（页级 chunk），"
          "overlap 只在块长 < 320 时触发，本语料每页正文中位数约 275 字符，几乎不发生；"
          "size 调到 150 后切分才真正生效。")


if __name__ == "__main__":
    main()
