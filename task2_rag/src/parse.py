# -*- coding: utf-8 -*-
"""T2-1 PDF 解析：按页抽文本，记录页码与标题层级。

输出 data/pages.jsonl，每行一个页面对象：
{
  "page": 1,                    # 1-based 物理页码（引用溯源的最小单元）
  "title": "页面主标题",         # 该页最大字号且非空的行（PPT 每页一个主题）
  "title_size": 32.0,
  "lines": [ {"text": ..., "size": ..., "y": ...}, ... ]  # 原始行（清洗前）
}

设计取舍：不使用 pymupdf4llm 的 markdown 模式——它按"文档流"输出，
无法给每行附带字号，也就做不了"字号>=20 是页标题"这个 PPT 特有的
层级判定。36 页 PPT 每页自带主题，按页取最大字号行当 section 名，
比通用文档解析规则更贴合这份原料。
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pymupdf

RAW_PDF = Path(__file__).resolve().parents[2] / "data_raw" / "Trendee品宣-公开版.pdf"
OUT = Path(__file__).resolve().parents[1] / "data" / "pages.jsonl"

TITLE_MIN_SIZE = 20.0  # 字号分布实测：>=20 仅出现在页标题/大数字，12-18 为正文

# 非法字符：替换符 U+FFFD、C0/C1 控制符（保留 \t\n\r）、代理区残字节
_BAD_REPLACEMENT = "\ufffd"


def sanitize(text: str) -> tuple[str, int]:
    """剔除非法字符并返回 (干净文本, 剔除数)。

    PDF 里可能夹带替换符（\ufffd）或 GBK 残字节（解码成代理区码点）；
    这些字符会让下游 jieba 分词产生空 token、让引用校验无法比对原句。
    这里只剔除、不改变合法字符——不做 NFKC，避免把中文全角标点折成半角、
    进而改变 chunk 长度基线。
    """
    kept, dropped = [], 0
    for ch in text:
        code = ord(ch)
        if ch == _BAD_REPLACEMENT:
            dropped += 1
            continue
        if code < 32 and ch not in "\t\n\r":
            dropped += 1
            continue
        if unicodedata.category(ch) in ("Cs", "Cn"):
            dropped += 1
            continue
        kept.append(ch)
    return "".join(kept), dropped


def parse_page(page: pymupdf.Page) -> tuple[dict, int]:
    d = page.get_text("dict")
    lines = []
    dropped_total = 0
    for block in d["blocks"]:
        if block["type"] != 0:  # 跳过图片块
            continue
        for line in block["lines"]:
            raw = "".join(s["text"] for s in line["spans"]).strip()
            text, dropped = sanitize(raw)
            dropped_total += dropped
            text = text.strip()
            if not text:
                continue
            size = max(s["size"] for s in line["spans"])
            lines.append({
                "text": text,
                "size": round(size, 1),
                "y": round(line["bbox"][1], 1),
                "x": round(line["bbox"][0], 1),
                "block": block["number"],  # 布局块号：PPT 多栏时，块=栏
            })
    # 阅读顺序：先按块分组（块内按 y），块间按 (列x, 块顶y)——
    # 多栏 PPT 直接按全局 y 排序会把左右栏交错，这是实测踩过的坑
    lines.sort(key=lambda l: (l["block"], l["y"]))
    blocks = {}
    for l in lines:
        blocks.setdefault(l["block"], []).append(l)
    ordered = sorted(
        (blk for blk in blocks.values()),
        key=lambda blk: (min(l["x"] for l in blk), min(l["y"] for l in blk)),
    )
    lines = [l for blk in ordered for l in blk]

    # 页标题：全页字号最大且长度合理（防止把图表大数字当标题）
    title, title_size = "", 0.0
    for l in lines:
        if l["size"] > title_size and 2 <= len(l["text"]) <= 40:
            title, title_size = l["text"], l["size"]
    if title_size < TITLE_MIN_SIZE:
        title = ""  # 最大字号都不够大，说明本页无明确标题

    return {
        "page": page.number + 1,
        "title": title,
        "title_size": title_size,
        "lines": lines,
    }, dropped_total


def main() -> None:
    doc = pymupdf.open(RAW_PDF)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    n_chars = 0
    n_dropped = 0
    with OUT.open("w", encoding="utf-8") as f:
        for page in doc:
            rec, dropped = parse_page(page)
            n_dropped += dropped
            n_chars += sum(len(l["text"]) for l in rec["lines"])
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"parsed {len(doc)} pages -> {OUT.name}, total {n_chars} chars")
    # 编码兜底的可诊断输出：剔除了多少非法字符必须可见，不能静默
    if n_dropped:
        print(f"[warn] dropped {n_dropped} illegal chars (U+FFFD / control / surrogate)")
    else:
        print("encoding check: 0 illegal chars (clean corpus)")


if __name__ == "__main__":
    main()
