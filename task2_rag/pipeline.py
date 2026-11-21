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

from src.retrieve import retrieve
from src.rerank import rerank
from src.context import build_context
from src.guard import guard, refusal_text
from src.cite_check import check


def run(topic: str, genre: str = "Blog", top_k: int = 20, use_llm_rerank: bool = False) -> dict:
    # 1) 检索 + 重排
    hits = rerank(topic, retrieve(topic, top_k=top_k),
                  mode="llm" if use_llm_rerank else "heuristic")
    # 2) 上下文
    context_text, sources = build_context(hits)
    # 3) 闸门：资料不足 → 拒答
    g = guard(topic, hits)
    result = {
        "topic": topic, "genre": genre,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "sources": sources,
        "guard": {"allowed": g.allowed, "reason": g.reason},
    }
    if not g.allowed:
        result["article"] = refusal_text(topic, g)
        result["refused"] = True
        result["cite_warnings"] = []
        return result

    # 4) 生成（无 Key → 离线证据包）
    system = (ROOT / "prompts" / "system.md").read_text(encoding="utf-8")
    user_tpl = (ROOT / "prompts" / "user.md").read_text(encoding="utf-8")
    user = user_tpl.replace("{topic}", topic).replace("{genre}", genre).replace("{context}", context_text)

    try:
        from src.generate import generate
        article = generate(system, user)
        result["mode"] = "generated"
    except RuntimeError as e:
        result["mode"] = "offline"
        result["offline_note"] = str(e)
        result["article"] = (
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
    result["article"] = clean
    result["cite_warnings"] = warns
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="RAG 品牌内容写作系统 CLI")
    ap.add_argument("topic")
    ap.add_argument("--genre", default="Blog", choices=["Blog", "FAQ", "品牌介绍", "产品介绍"])
    ap.add_argument("--top-k", type=int, default=20)
    ap.add_argument("--llm-rerank", action="store_true", help="有 Key 时用 LLM 重排")
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()

    r = run(args.topic, args.genre, args.top_k, args.llm_rerank)
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
