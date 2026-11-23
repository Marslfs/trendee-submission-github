# -*- coding: utf-8 -*-
"""生成「07 上下文」说明卡片 PNG。数字来自实测。"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = "C:/Windows/Fonts/msyh.ttc"
FONT_BD = "C:/Windows/Fonts/msyhbd.ttc"

W, PAD = 1360, 56
CONTENT = W - PAD * 2

INK = (26, 26, 26)
INK2 = (90, 90, 90)
INK3 = (140, 140, 140)
LINE = (226, 226, 222)
TEAL = (29, 158, 117)
TEAL_BG = (240, 250, 246)
AMBER = (186, 117, 23)
AMBER_BG = (253, 246, 234)
GRAY_BG = (247, 247, 245)
GRAY_BD = (200, 199, 193)
RED = (163, 45, 45)
BLUE = (24, 95, 165)
BLUE_BG = (230, 241, 251)


def f(size, bold=False):
    return ImageFont.truetype(FONT_BD if bold else FONT, size)


F_TITLE = f(42, True)
F_SUB = f(22)
F_SEC = f(28, True)
F_BODY = f(21)
F_BODY_BD = f(21, True)
F_SM = f(19)
F_TAB = f(20)
F_TAB_BD = f(20, True)
F_CODE = f(19)


def wrap(s, font, maxw):
    lines, cur = [], ""
    for ch in s:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if font.getlength(cur + ch) > maxw:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


img = Image.new("RGB", (W, 2400), (255, 255, 255))
d = ImageDraw.Draw(img)
y = 52

d.text((PAD, y), "上下文构建：六个块变成 [S1]…[S6]，每块都能回到 PDF 页码", font=F_TITLE, fill=INK)
y += 60
d.text((PAD, y), "这一步不改内容，只做三件事：编号、贴地址、控预算 —— 你想到两件，第三件是预算", font=F_SUB, fill=INK2)
y += 50


def section(title, y):
    d.rectangle([PAD, y + 3, PAD + 4, y + 31], fill=TEAL)
    d.text((PAD + 16, y), title, font=F_SEC, fill=INK)
    return y + 50


# ---------- ① 两件事 ----------
y = section("① 你理解的两件事，都对", y)
bw = (CONTENT - 24) // 2
bh = 300
for idx, (head, sub) in enumerate([("拼：6 块正文拼成一段纯文本", "按重排顺序，每块抬头带编号和地址"),
                                  ("记：sources 表 6 行，可回溯", "sid / chunk_id / page / section / text / score")]):
    x0 = PAD + idx * (bw + 24)
    d.rounded_rectangle([x0, y, x0 + bw, y + bh], radius=12, fill=TEAL_BG, outline=TEAL, width=2)
    d.text((x0 + 22, y + 18), head, font=F_BODY_BD, fill=TEAL)
    d.text((x0 + 22, y + 48), sub, font=F_SM, fill=INK2)

# 左：真实上下文片段
code_lines = [
    "[S1] (page 4 | 为什么选择LLM-原生GEO?)",
    "为什么选择LLM-原生GEO? LLM-原生 GEO让好的品牌",
    "进入AI的“长期记忆” LLM-原生GEO : 深度适配大语言",
    "模型 (LLM) 底层架构及 其交互逻辑的技术体系…",
    "",
    "[S2] (page 12 | GEO时代到来：AI投毒乱象)",
]
cy = y + 86
d.rounded_rectangle([PAD + 16, cy - 8, PAD + bw - 16, cy + 6 + 27 * len(code_lines)],
                    radius=8, fill=(255, 255, 255), outline=GRAY_BD, width=1)
for ln in code_lines:
    d.text((PAD + 30, cy), ln, font=F_CODE, fill=INK if ln.startswith("[") else INK2)
    cy += 27

# 右：sources 表
x1 = PAD + bw + 24
sy = y + 86
d.text((x1 + 22, sy), "sources[0] = {", font=F_CODE, fill=INK2)
sy += 27
for k, v in [("sid", "'S1'"), ("chunk_id", "'p004-0'"), ("page", "4"),
             ("section", "'为什么选择LLM-原生GEO?'"), ("text", "<原文全文，未截断>"),
             ("score", "0.9361  # rerank 分")]:
    d.text((x1 + 38, sy), k, font=F_CODE, fill=BLUE)
    d.text((x1 + 132, sy), v, font=F_CODE, fill=INK)
    sy += 25
d.text((x1 + 22, sy), "}", font=F_CODE, fill=INK2)
y += bh + 44

# ---------- ② SID 是位置号 ----------
y = section("② 要拧紧的一点：SID 是位置号，不是身份证", y)
chain = [("[S1]", "本轮排序第 1 名"), ("chunk_id", "p004-0"), ("page 4", "PDF 第 4 页"), ("section", "章节名")]
cx = PAD
for i, (a, b) in enumerate(chain):
    w_ = max(d.textlength(a, font=F_TAB_BD), d.textlength(b, font=F_SM)) + 40
    d.rounded_rectangle([cx, y, cx + w_, y + 66], radius=10,
                        fill=GRAY_BG if i else BLUE_BG, outline=GRAY_BD if i else BLUE, width=1)
    d.text((cx + w_ / 2, y + 12), a, font=F_TAB_BD, fill=INK if i else BLUE, anchor="ma")
    d.text((cx + w_ / 2, y + 40), b, font=F_SM, fill=INK2, anchor="ma")
    cx += w_
    if i < len(chain) - 1:
        d.line([cx + 6, y + 33, cx + 30, y + 33], fill=INK3, width=2)
        d.polygon([(cx + 30, y + 28), (cx + 38, y + 33), (cx + 30, y + 38)], fill=INK3)
        cx += 44
y += 66 + 20
note = "换一个主题，S1 可能变成另一块 —— 它只说明「本轮第几名」。真正不变的身份是 chunk_id（p004-0 = 第 4 页第 0 块），这也是 cite_check 能回查的原因。"
for ln in wrap(note, F_BODY, CONTENT):
    d.text((PAD, y), ln, font=F_BODY, fill=INK2)
    y += 30
y += 24

# ---------- ③ 第三件事：预算 ----------
y = section("③ 你没提到的第三件事：3000 字符预算 + 句子级截断", y)
items = [
    ("超预算怎么办", "从后往前整块丢，剩余空间 ≤50 字就直接 break —— 宁可少一块，不塞半块"),
    ("最后一块超了怎么办", "在预算内找最后一个句末标点（。！？；）切开；找不到才硬切（实测：预算 300 → 切在「主动推荐。」，预算 200 → 切在「语义向量。」）"),
    ("本语料实际有没有触发", "六块正文 1619 字 + 抬头 242 字 = 1861 字，预算 3000 根本没用上 —— 这段裁剪在本语料是死代码，参数化是为将来换大语料"),
]
for head, body in items:
    d.text((PAD + 4, y + 2), "·", font=F_BODY_BD, fill=TEAL)
    d.text((PAD + 24, y), head, font=F_BODY_BD, fill=INK)
    hy = y + 32
    for ln in wrap(body, F_SM, CONTENT - 24):
        d.text((PAD + 24, hy), ln, font=F_SM, fill=INK2)
        hy += 27
    y = hy + 14
y += 10

# ---------- ④ 细节 ----------
y = section("④ 一个容易被问倒的细节", y)
d.rounded_rectangle([PAD, y, PAD + CONTENT, y + 118], radius=12, fill=AMBER_BG, outline=(228, 199, 152), width=1)
d.text((PAD + 22, y + 16), "sources 里存的是原文全文，截断只发生在拼给 LLM 的那一份", font=F_BODY_BD, fill=AMBER)
for i, ln in enumerate(wrap("好处：cite_check 能拿完整原文做词面重叠校验，不被截断坑到。隐患：若某块被截断，模型引用了「它没看到的句子」也照样通过校验 —— 本语料预算不触发，但换大语料要先修。", F_SM, CONTENT - 44)):
    d.text((PAD + 22, y + 52 + i * 27), ln, font=F_SM, fill=INK)
y += 118 + 40

# ---------- ⑤ 六块体量 ----------
y = section("⑤ 本次实际送进去的六块（正文字符数）", y)
data = [("S1", "p004-0", 333), ("S2", "p012-0", 330), ("S3", "p032-0", 255),
        ("S4", "p002-1", 384), ("S5", "p014-0", 181), ("S6", "p003-0", 136)]
maxv = max(v for _, _, v in data)
barx = PAD + 210
maxw = 420
for sid, cid, v in data:
    d.text((PAD, y + 4), sid, font=F_TAB_BD, fill=BLUE)
    d.text((PAD + 48, y + 4), cid, font=F_TAB, fill=INK2)
    w_ = max(6, int(maxw * v / maxv))
    d.rounded_rectangle([barx, y + 2, barx + w_, y + 28], radius=6, fill=(158, 216, 197))
    d.text((barx + w_ + 12, y + 4), str(v), font=F_TAB, fill=INK)
    y += 40
d.text((barx + maxw + 20, y + 6), "六块合计 1619 字（+ 抬头 242 = 送进 LLM 1861 字）", font=F_TAB_BD, fill=TEAL)
y += 40
y += 26

d.rounded_rectangle([PAD, y, PAD + CONTENT, y + 74], radius=12, fill=TEAL_BG, outline=TEAL, width=2)
d.text((PAD + 26, y + 20), "一句话：上下文层不改内容，只把六个散块变成一段带地址的编号文本。",
       font=f(24, True), fill=TEAL)
y += 74 + 52

img = img.crop((0, 0, W, y))
out = Path(__file__).with_name("context_card.png")
img.save(out)
print(out, img.size)
