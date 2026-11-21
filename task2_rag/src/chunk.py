# -*- coding: utf-8 -*-
"""T2-3 Chunk：标题感知切分 + 参数化（size/overlap）。

输入 data/pages_clean.jsonl → 输出 data/chunks.jsonl：
{
  "chunk_id": "p002-0",      # 页号-页内序号，稳定可复现
  "page": 2,                 # 引用溯源的最小单元
  "section": "我们的愿景：让好的品牌进入AI的深度记忆",
  "text": "...",
  "n_chars": 398,
}

策略（面试能讲的取舍）：
- 不按固定 512 字符硬切：硬切会把图表和它的表头切开，检索到半张表
  比检索不到更糟。以"段落"为最小不可分单元。
- size≈400 / overlap≈80：偏小块利于精准命中，靠 overlap + section
  路径补上下文；大块召回准但塞满上下文，引用页码指到一大段，溯源变弱。
- 每块正文前拼上 section 标题：保证块脱离页面后仍自解释，
  同时让 BM25 命中标题词（标题是作者标注的主题词）。
"""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
IN, OUT = DATA / "pages_clean.jsonl", DATA / "chunks.jsonl"

CHUNK_SIZE = 400   # 单块目标字符数
OVERLAP = 80       # 相邻块重叠字符数
MIN_CHARS = 20     # 低于此长度的碎片并入前块，避免"半句话块"


def split_page(page: dict, size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[dict]:
    paras = [s for s in page["paras"] if s.strip()]
    if not paras:
        return []
    section = page["title"] or f"第{page['page']}页"

    # 贪心装块：段为单位，不切断句子
    chunks: list[list[str]] = []
    cur: list[str] = []
    cur_len = 0
    for p in paras:
        if cur and cur_len + len(p) > size:
            chunks.append(cur)
            cur, cur_len = [], 0
        cur.append(p)
        cur_len += len(p)
    if cur:
        chunks.append(cur)

    # overlap：下一块开头回借上一块尾部整段（不切割句子），借到约 overlap 为止
    out = []
    for i, blk in enumerate(chunks):
        text_parts = list(blk)
        if i > 0 and sum(len(x) for x in blk) < size * 0.8:
            borrowed, bl = [], 0
            for p in reversed(chunks[i - 1]):
                if bl + len(p) > overlap:
                    break
                borrowed.insert(0, p)
                bl += len(p)
            text_parts = borrowed + text_parts
        text = " ".join(text_parts)
        # 碎片并入前块
        if out and len(text) < MIN_CHARS:
            out[-1]["text"] += " " + text
            continue
        out.append({
            "chunk_id": f"p{page['page']:03d}-{len(out)}",
            "page": page["page"],
            "section": section,
            "text": text,
            "n_chars": len(text),
        })
    return out


def main(size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> int:
    pages = [json.loads(x) for x in IN.read_text(encoding="utf-8").splitlines()]
    total = 0
    with OUT.open("w", encoding="utf-8") as f:
        for p in pages:
            for c in split_page(p, size, overlap):
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
                total += 1
    lens = [c["n_chars"] for c in (json.loads(x) for x in OUT.read_text(encoding="utf-8").splitlines())]
    print(f"chunks: {total} (size={size}, overlap={overlap})")
    print(f"  len min/avg/max = {min(lens)}/{sum(lens)//len(lens)}/{max(lens)}")
    pages_covered = {json.loads(x)["page"] for x in OUT.read_text(encoding="utf-8").splitlines()}
    print(f"  pages covered: {len(pages_covered)}/{len(pages)}")
    return total


if __name__ == "__main__":
    main()
