# -*- coding: utf-8 -*-
"""T2-12 Demo：Streamlit 单页。左侧输入主题 → 右侧文章 + 引用卡片 + 原文片段。

启动：streamlit run app.py
核心逻辑直接复用 pipeline.run()，UI 只是壳——保证 Demo 与 CLI 行为一致。
"""
from __future__ import annotations

import streamlit as st

from pipeline import run

st.set_page_config(page_title="Trendee RAG 写作系统", page_icon="📝", layout="wide")

EXAMPLES = [
    "为什么中国出海品牌需要进行 GEO 优化",
    "Trendee 的 LLM-原生 GEO 技术架构",
    "AI 问答引擎的工作原理与 GEO 的关系",
    "万悉科技的客户名单和融资历史",  # 语料外主题：演示拒答
]

st.title("📝 Trendee RAG 品牌内容写作系统")
st.caption("基于万悉科技品宣 PDF · 检索 → 重排 → 编号上下文 → 闸门 → 生成 → 引用校验")

with st.sidebar:
    st.header("⚙️ 参数")
    genre = st.selectbox("文章类型", ["Blog", "FAQ", "品牌介绍", "产品介绍"])
    top_k = st.slider("候选召回数 top-k", 5, 40, 20)
    use_llm_rerank = st.checkbox("LLM 重排（需 API Key，缺则自动降级启发式）", value=False)
    st.divider()
    st.subheader("示例主题")
    st.markdown("点击填入输入框：")
    for ex in EXAMPLES:
        if st.button(ex, use_container_width=True, key=ex):
            st.session_state["topic"] = ex

topic = st.text_input("主题", value=EXAMPLES[0], key="topic_input")
go = st.button("🚀 生成", type="primary", use_container_width=True)

if go:
    if not topic.strip():
        st.warning("主题不能为空：请给出一个可检索的主题（如「为什么中国出海品牌需要 GEO」）")
        st.stop()

    with st.spinner("检索 → 重排 → 构建上下文 → 生成 → 引用校验…"):
        try:
            r = run(topic.strip(), genre=genre, top_k=top_k, use_llm_rerank=use_llm_rerank)
        except ValueError as e:      # 与 CLI 同一套入参规则，报错文案一致
            st.error(str(e))
            st.stop()

    # 索引新鲜度：chunks 变了但索引没重建 → 引用可能指错页，必须显式提示
    idx = r.get("index_check") or {}
    if idx and not idx.get("ok"):
        st.warning(f"⚠️ 索引校验未通过：{idx.get('message')}")

    # 状态行
    col1, col2, col3 = st.columns(3)
    gmode = r["guard"].get("mode")
    if r.get("refused"):
        col1.error("🛑 拒答（资料不足）")
    elif gmode == "degrade":
        col1.warning("⚠️ 降级生成（覆盖度不足）")
    else:
        mode = r.get("mode", "")
        col1.success("✅ 生成完成" if mode == "generated" else "⚠️ 离线模式（无 Key，仅证据包）")
    col2.metric("来源数", len(r["sources"]))
    col3.metric("引用告警", len(r["cite_warnings"]))

    if gmode == "degrade":
        st.warning(r.get("degrade_notice")
                   or "⚠️ 资料覆盖度不足，本文仅基于已检索到的片段，未覆盖部分不作推断。")

    if r.get("refused"):
        st.markdown(r["article"])
    else:
        left, right = st.columns([3, 2])

        with left:
            st.subheader("文章")
            st.markdown(r["article"])
            if r["cite_warnings"]:
                st.warning("**引用校验告警**（已自动降级）\n\n" + "\n\n".join(f"- {w}" for w in r["cite_warnings"]))
            if r.get("mode") == "offline":
                st.info(r.get("offline_note", ""))
                with st.expander("构建好的 Prompt（离线模式证据）"):
                    st.text(r.get("prompts", {}).get("user", ""))

        with right:
            st.subheader("引用依据")
            for s in r["sources"]:
                with st.expander(f"[{s['sid']}] 第 {s['page']} 页 · {s['section'][:22]}"):
                    st.markdown(f"**chunk**: `{s['chunk_id']}` · 相关度 `{s.get('score')}`")
                    st.markdown(s["text"])

    st.divider()
    st.caption(f"guard: {r['guard'].get('reason') or '通过'}")
    with st.expander("原始 JSON"):
        st.json(r)
