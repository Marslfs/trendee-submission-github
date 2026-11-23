# -*- coding: utf-8 -*-
"""全链路 CLI：一条命令跑完 检索→重排→上下文→闸门→生成→引用校验。

用法（在 task2_rag/ 下）：
  python -m pipeline "为什么中国出海品牌需要进行 GEO 优化"              # Blog
  python -m pipeline "Trendee 的 GEO 服务包含哪些能力" --genre FAQ     # FAQ
  python -m pipeline "客户名单" --top-k 8                               # 会被 guard 拒答

无 OPENAI_API_KEY 时自动降级为离线模式：输出检索证据包
（top 片段 + 构建好的上下文 + prompt），生成环节留接口。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "eval" / "outputs"

# B9：--genre 支持 4 种文体，各自有独立 user 模板（首句均参数化为 {genre}）。
# 未知 genre 回退 prompts/user.md（兼容旧调用）。
GENRE_TEMPLATES = {
    "Blog": "user_blog.md",
    "FAQ": "user_faq.md",
    "品牌介绍": "user_brand.md",
    "产品介绍": "user_product.md",
}

from src.retrieve import retrieve
from src.rerank import rerank
from src.context import build_context
from src.guard import guard, refusal_text
from src.cite_check import check
from src.index import check_freshness

MAX_TOP_K = 50                     # 入参上限：--top-k 200 对 40 块语料毫无意义，还给滥用留口子


def validate_inputs(topic: str, top_k: int) -> str:
    """入参校验（CLI 与 app.py 共用同一套规则，避免两处行为不一致）。"""
    t = (topic or "").strip()
    if not t:
        raise ValueError("主题不能为空：请给出一个可检索的主题（如「为什么中国出海品牌需要 GEO」）")
    if not any(ch.isalnum() for ch in t):
        raise ValueError(f"主题「{t}」不含任何文字或数字，无法检索——请用自然语言描述主题")
    if top_k < 1 or top_k > MAX_TOP_K:
        raise ValueError(f"top_k 必须在 1~{MAX_TOP_K}（当前 {top_k}）；语料只有 40 块，超过上限没有意义")
    return t


def run(topic: str, genre: str = "Blog", top_k: int = 20, use_llm_rerank: bool = False) -> dict:
    topic = validate_inputs(topic, top_k)
    # 0) 索引新鲜度：chunks 变了但索引没重建时，[Sn] 会静默指错页 —— 必须显式告警
    fresh_ok, fresh_msg = check_freshness()
    if not fresh_ok:
        from loguru import logger
        logger.warning(f"索引校验未通过：{fresh_msg}")
    # 1) 检索 + 重排
    hits = rerank(topic, retrieve(topic, top_k=top_k),
                  mode="llm" if use_llm_rerank else "heuristic")
    # 2) 上下文
    context_text, sources = build_context(hits)
    # 3) 闸门：资料不足 → 拒答
    g = guard(topic, hits)
    # C1：degrade 时在文章开头插入显式覆盖度声明（cite_check 之后再拼，声明不受引用校验影响）
    notice = ""
    if g.mode == "degrade":
        notice = (f"> ⚠️ 资料覆盖度说明：本次检索只覆盖主题词 {g.coverage:.0%}，"
                  f"以下结论仅基于 PDF 中相关片段（{len(sources)} 个来源），未覆盖部分不作推断。\n\n")
    result = {
        "topic": topic, "genre": genre,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "sources": sources,
        "guard": {"allowed": g.allowed, "mode": g.mode,
                  "coverage": round(g.coverage, 4), "reason": g.reason},
        "degrade_notice": notice,
        # 把语料指纹写进产物：日后复现时可比对，判断 [Sn] 是否可能已失效
        "index_check": {"ok": fresh_ok, "message": fresh_msg},
    }
    if not g.allowed:
        result["article"] = refusal_text(topic, g)
        result["refused"] = True
        result["cite_warnings"] = []
        return result

    # 4) 生成（无 Key → 离线证据包）
    system = (ROOT / "prompts" / "system.md").read_text(encoding="utf-8")
    tpl_name = GENRE_TEMPLATES.get(genre, "user.md")
    user_tpl = (ROOT / "prompts" / tpl_name).read_text(encoding="utf-8")
    user = user_tpl.replace("{topic}", topic).replace("{genre}", genre).replace("{context}", context_text)

    try:
        from src.generate import generate
        article = generate(system, user)
        result["mode"] = "generated"
    except RuntimeError as e:
        result["mode"] = "offline"
        result["offline_note"] = str(e)
        result["article"] = notice + (
            f"# [离线模式] 主题：{topic}\n\n生成环节需要 LLM_API_KEY（.env）。"
            f"以下为已构建好的上下文与 Prompt，注入 Key 后重跑本命令即可出文章。\n\n"
            f"## 检索证据（top {len(sources)}）\n\n{context_text}\n\n"
            f"## System Prompt 已就绪\n\n见 prompts/system.md（角色+铁律+输出结构）"
        )
        result["cite_warnings"] = []
        result["prompts"] = {"system": system, "user": user}
        return result

    # 5) 引用校验（编号越界 + 词面重叠），未命中降级
    clean, warns = check(article, sources)
    # 声明在引用校验之后拼入：声明本身不含 [Sn]，不参与词面重叠校验
    result["article"] = notice + clean
    result["cite_warnings"] = warns
    return result


def _top_k_arg(v: str) -> int:
    try:
        n = int(v)
    except ValueError:
        raise argparse.ArgumentTypeError(f"--top-k 需为整数，收到 {v!r}")
    if not 1 <= n <= MAX_TOP_K:
        raise argparse.ArgumentTypeError(f"--top-k 必须在 1~{MAX_TOP_K} 之间（收到 {n}）")
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description="RAG 品牌内容写作系统 CLI")
    ap.add_argument("topic")
    ap.add_argument("--genre", default="Blog", choices=["Blog", "FAQ", "品牌介绍", "产品介绍"])
    ap.add_argument("--top-k", type=_top_k_arg, default=20)
    ap.add_argument("--llm-rerank", action="store_true", help="有 Key 时用 LLM 重排")
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()

    try:
        r = run(args.topic, args.genre, args.top_k, args.llm_rerank)
    except ValueError as e:            # 空主题 / 纯符号主题 / top-k 越界：明确报错，不抛栈
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps({k: r[k] for k in ("topic", "mode", "refused", "guard") if k in r},
                     ensure_ascii=False, indent=2))
    print("\n" + "=" * 60 + "\n")
    print(r["article"])
    if r["cite_warnings"]:
        print("\n" + "=" * 60 + "\n引用校验告警:")
        for w in r["cite_warnings"]:
            print("  ⚠", w)

    if not args.no_save:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        slug = datetime.now().strftime("%H%M%S")
        path = OUT_DIR / f"{args.genre}-{slug}.json"
        path.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[saved] {path}")


if __name__ == "__main__":
    main()
