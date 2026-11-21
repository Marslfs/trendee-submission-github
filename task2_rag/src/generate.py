# -*- coding: utf-8 -*-
"""T2-9 生成：OpenAI 兼容接口，可切模型，超时与重试。

换供应商 = 改 .env 两个变量（base_url / model），代码零改动：
    OPENAI_API_KEY=sk-xxx          # 任一 OpenAI 兼容服务
    OPENAI_BASE_URL=https://api.deepseek.com   # 或通义/月之暗面/本地 vLLM
    OPENAI_MODEL=deepseek-chat

无 Key 时 get_client() 抛 RuntimeError——pipeline 会走"离线模式"，
输出检索包与上下文，生成环节留待 Key 注入，链路其他环节全部可验。
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT.parent / ".env")  # 仓库根目录 .env（不入 git）
load_dotenv(ROOT / ".env")          # 也支持 task2_rag/.env

MAX_RETRIES, TIMEOUT = 2, 120


def get_client():
    """返回 (client, model)。缺 Key/依赖时抛 RuntimeError（调用方降级）。"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("未配置 OPENAI_API_KEY（.env），生成环节不可用，链路其余环节可离线验证")
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError(f"openai 包未安装：{e}") from e
    base = os.getenv("OPENAI_BASE_URL") or None
    model = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    return OpenAI(api_key=api_key, base_url=base, timeout=TIMEOUT), model


def generate(system: str, user: str, temperature: float = 0.4) -> str:
    client, model = get_client()
    last_err = None
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=temperature,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:  # 网络抖动/限流：指数退避重试
            last_err = e
            logger.warning(f"attempt {attempt} failed: {e}")
            if attempt <= MAX_RETRIES:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"生成失败（已重试 {MAX_RETRIES} 次）：{last_err}")
