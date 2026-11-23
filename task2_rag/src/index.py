# -*- coding: utf-8 -*-
"""T2-4 索引：jieba 分词 → BM25 倒排索引，落盘可复用。

输出 data/index/：
  bm25.pkl       # rank_bm25 对象（含词表与倒排）
  chunks.jsonl   # 索引时 chunk 顺序的快照（检索按行号对齐，避免漂移）

为什么 BM25 而不是纯向量（题面追问点）：
- 原料是品宣 PPT，充满专有名词与数字："GEO""LLM 原生""65% 引用率"。
  稀疏检索对这类词是精确匹配，向量检索容易把它们抹平成"语义相近的别的话"。
- 36 页 / 40 块的规模，BM25 毫秒级，零模型零下载。
- 向量索引留接口：retrieve.py 的 hybrid 入口已把两路融合（RRF）写好，
  有 API Key 时 dense 一路可插入，架构不用动。
"""
from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path

import jieba
from rank_bm25 import BM25Okapi

DATA = Path(__file__).resolve().parents[1] / "data"
INDEX_DIR = DATA / "index"
META = INDEX_DIR / "meta.json"

# 领域词进词表：防止 jieba 把 "GEO" 切成单字符、把 "品宣" 切散
DOMAIN_WORDS = [
    "GEO", "LLM", "RAG", "Trendee", "万悉科技", "品宣", "生成式引擎优化",
    "AI问答", "问答引擎", "引用率", "可见性", "深度记忆", "大模型",
    "检索增强", "引用溯源", "知识图谱", "Embedding", "Prompt",
    "出海品牌", "内容营销", "结构化数据", "JSON-LD", "合规",
]
for w in DOMAIN_WORDS:
    jieba.add_word(w, freq=1000)

STOPWORDS = set("的 了 是 在 和 与 或 及 而 把 对 从 被 让 使 向 于 由 以 按 为 之 其 本 该 此 等 即 并 且 但 又 再 也 都 很 更 最 就 才 会 能 可 要 有 无 没有 及其 通过 对于 关于 因此 所以 如果 那么 以及 我们 你们 他们 它 这 那 一下 一些 一下".split())


def tokenize(text: str) -> list[str]:
    return [t for t in jieba.lcut(text.lower()) if t.strip() and t not in STOPWORDS and not t.isspace()]


def fingerprint_of(chunks: list[dict]) -> str:
    """语料指纹：chunk_id + page + text 的 sha256。

    chunk_id 里含页码（p003-0），所以「PDF 插一页」会让后续所有 chunk_id 平移。
    指纹变了的含义很明确：**已落盘文章里的 [S3] 可能指向了别的页**。
    """
    h = hashlib.sha256()
    for c in chunks:
        h.update(f"{c['chunk_id']}|{c['page']}|{c['text']}".encode("utf-8"))
    return h.hexdigest()


def write_meta(chunks: list[dict], index_dir: Path = INDEX_DIR) -> dict:
    pages = sorted({c["page"] for c in chunks})
    meta = {
        "n_chunks": len(chunks),
        "n_pages": len(pages),
        "page_min": pages[0] if pages else 0,
        "page_max": pages[-1] if pages else 0,
        "sha256": fingerprint_of(chunks),
    }
    (index_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def check_freshness(data_dir: Path = DATA, index_dir: Path = INDEX_DIR) -> tuple[bool, str]:
    """索引与当前语料是否一致（T2-I I2：换语料后引用失效检测）。

    场景：`chunk.py` 重切了 `data/chunks.jsonl`，但忘了重跑 `index.py`——
    此时检索仍打旧索引，引用编号与页码对不上，且没有任何报错。
    返回 (ok, message)；调用方负责把 message 打到日志/Demo 上，不静默。
    """
    meta_p = index_dir / "meta.json"
    if not meta_p.exists():
        return False, "索引缺少 meta.json（旧索引）：无法确认与语料是否一致，请重跑 python -m src.index"
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    corpus_p = data_dir / "chunks.jsonl"
    if not corpus_p.exists():
        return False, f"语料文件不存在：{corpus_p}，请先跑 chunk.py"
    chunks = [json.loads(x) for x in corpus_p.read_text(encoding="utf-8").splitlines() if x.strip()]
    cur = fingerprint_of(chunks)
    if cur != meta.get("sha256"):
        return False, (f"索引与语料不一致：语料 sha={cur[:12]} / 索引 sha={str(meta.get('sha256'))[:12]}，"
                       f"chunks 已变更但索引未重建——已落盘文章的 [Sn] 可能指向旧页，"
                       f"请重跑 python -m src.index")
    return True, (f"索引与语料一致：{meta['n_chunks']} chunks / {meta['n_pages']} 页，"
                  f"sha={cur[:12]}")


def main() -> int:
    chunks = [json.loads(x) for x in (DATA / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    corpus = [tokenize(f"{c['section']} {c['text']}") for c in chunks]  # 标题一并进索引
    bm25 = BM25Okapi(corpus)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    (INDEX_DIR / "bm25.pkl").write_bytes(pickle.dumps(bm25))
    (INDEX_DIR / "chunks.jsonl").write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chunks), encoding="utf-8")
    meta = write_meta(chunks)

    # 自检：用一个典型查询验证索引可用
    probe = tokenize("GEO 优化")
    scores = bm25.get_scores(probe)
    top = sorted(range(len(chunks)), key=lambda i: -scores[i])[:3]
    print(f"indexed {len(chunks)} chunks -> {INDEX_DIR}")
    print(f"fingerprint: {meta['sha256'][:16]} ({meta['n_pages']} 页)")
    print("probe 'GEO 优化' top3:")
    for i in top:
        print(f"  [{chunks[i]['chunk_id']}] {chunks[i]['section'][:24]} (score={scores[i]:.1f})")
    return len(chunks)


if __name__ == "__main__":
    main()
