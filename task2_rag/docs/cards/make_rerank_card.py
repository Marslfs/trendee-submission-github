# -*- coding: utf-8 -*-
"""生成「06 重排」说明卡片 PNG。数据全部来自实测消融，非估算。"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = "C:/Windows/Fonts/msyh.ttc"
FONT_BD = "C:/Windows/Fonts/msyhbd.ttc"
MONO = "C:/Windows/Fonts/consola.ttf"

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


def fm(size):
    return ImageFont.truetype(MONO, size)


F_TITLE = f(42, True)
F_SUB = f(22)
F_SEC = f(28, True)
F_BODY = f(21)
F_BODY_BD = f(21, True)
F_SM = f(19)
F_TAB = f(20)
F_TAB_BD = f(20, True)
F_MONO = fm(19)


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

d.text((PAD, y), "重排：20 → 6，真正改变排序的只有两个加项", font=F_TITLE, fill=INK)
y += 60
d.text((PAD, y), "一条公式四个加项 + 消融实测（主题：为什么中国出海品牌需要进行 GEO 优化）", font=F_SUB, fill=INK2)
y += 50


def section(title, y, note=None):
    d.rectangle([PAD, y + 3, PAD + 4, y + 31], fill=TEAL)
    d.text((PAD + 16, y), title, font=F_SEC, fill=INK)
    y += 46
    if note:
        for ln in wrap(note, F_BODY, CONTENT):
            d.text((PAD, y), ln, font=F_BODY, fill=INK2)
            y += 30
    return y + 8


# ---------- ① 上游留下的问题 ----------
y = section("① 上游留了个坑：融合分是相对分，不能直接取前 6", y)
bullets = [
    ("每路先 ÷ 自己的 max 再加总", "→ 单路线查询最高块恒为 1.0，五路线满分 5.0"),
    ("所以分数只在同一次查询内部可比", "→ 换个主题，3.35 和 1.0 谁更相关说不清"),
    ("需要 0~1 的单调映射做锚", "→ score/(score+1)，把无上界的 BM25 压进 0~1"),
]
for a, b in bullets:
    d.text((PAD + 4, y + 3), "·", font=F_BODY_BD, fill=TEAL)
    d.text((PAD + 24, y), a, font=F_BODY_BD, fill=INK)
    d.text((PAD + 24 + d.textlength(a, font=F_BODY_BD) + 10, y), b, font=F_BODY, fill=INK2)
    y += 34
y += 14

# ---------- ② 公式 ----------
y = section("② 一条公式：一个基准 + 三个加项", y)
fy = y
d.rounded_rectangle([PAD, fy, PAD + CONTENT, fy + 128], radius=12, fill=GRAY_BG, outline=GRAY_BD, width=1)
lines = [
    ("rerank  =  score / (score + 1)", "① 基准：0~1 单调映射，本身不改变顺序", BLUE),
    ("        +  0.6 × 主题词命中 section 标题的比例", "② 标题项：唯一能翻盘的强信号", TEAL),
    ("        −  0.5（<60 字）  /  − 0.1（>400 字）", "③ 长度项：拦封面碎片、压超长块", AMBER),
    ("        +  0.05 × (10 − 名次) / 10", "④ 先验项：前 10 名平滑，防抖动", INK3),
]
ty = fy + 16
for code, desc, color in lines:
    d.text((PAD + 22, ty), code, font=F_TAB_BD, fill=color)
    d.text((PAD + 22 + d.textlength(code, font=F_TAB_BD) + 18, ty), desc, font=F_SM, fill=INK2)
    ty += 27
y = fy + 128 + 22

d.text((PAD, y), "真实翻盘一例：", font=F_BODY_BD, fill=INK)
y += 34
cols = [(PAD, "块"), (PAD + 92, "fused"), (PAD + 182, "base"), (PAD + 262, "标题项"),
        (PAD + 368, "长度"), (PAD + 438, "先验"), (PAD + 508, "final"), (PAD + 596, "名次变化")]
for cx, txt in cols:
    d.text((cx, y), txt, font=F_SM, fill=INK3)
y += 28
examples = [
    ("p002-1", "3.349", "0.770", "0.00", "0", "0.050", "0.820", "第 1 → 第 4", RED),
    ("p004-0", "2.568", "0.720", "0.17", "0", "0.045", "0.936", "第 2 → 第 1", TEAL),
]
for cid, fu, ba, ti, ln_, bo, fi, mv, color in examples:
    d.rounded_rectangle([PAD - 8, y - 6, PAD + CONTENT, y + 30], radius=8,
                        fill=TEAL_BG if color == TEAL else (253, 240, 240))
    vals = [cid, fu, ba, ti, ln_, bo, fi]
    for (cx, _), v in zip(cols[:7], vals):
        d.text((cx, y), v, font=F_TAB if v != cid else F_TAB_BD, fill=INK)
    d.text((cols[7][0], y), mv, font=F_TAB_BD, fill=color)
    y += 40
y += 10
for ln in wrap("两者 base 只差 0.050，而标题项一次给 0.17 —— 0.6 这个系数的全部意义就是「让标题命中的块翻盘」。", F_BODY, CONTENT):
    d.text((PAD, y), ln, font=F_BODY, fill=INK2)
    y += 30
y += 22

# ---------- ③ 消融 ----------
y = section("③ 消融实测：三个系数谁真在干活", y)
d.text((PAD, y), "固定 top20 候选，逐项打开，看前 6 名的排序有没有变（两个主题对照）", font=F_SM, fill=INK2)
y += 32

col_x = [PAD, PAD + 300, PAD + 690]
col_w = [300, 390, CONTENT - 690 - 0]
d.rectangle([PAD, y, PAD + CONTENT, y + 40], fill=(243, 243, 240))
for cx, h in zip(col_x, ["打开哪一项", "主题一：GEO 优化", "主题二：技术架构"]):
    d.text((cx + 14, y + 10), h, font=F_TAB_BD, fill=INK)
y += 40

rows = [
    ("A  只有 base（= 不重排）", "基准", INK3, "基准", INK3),
    ("B  + 标题项", "6 位全变（p004-0 登顶）", TEAL, "5 位变化", TEAL),
    ("C  + 长度项", "无变化 —— top20 里没有 <60 字的块", RED, "5 位变化（p028-0 417 字被压 0.1）", TEAL),
    ("D  + 先验项", "无变化", RED, "无变化", RED),
    ("E  全部打开（实际跑）", "同 B", INK2, "6 位变化", INK2),
]
for a, b1, c1, b2, c2 in rows:
    d.line([PAD, y + 40, PAD + CONTENT, y + 40], fill=LINE, width=1)
    d.text((col_x[0] + 14, y + 10), a, font=F_TAB, fill=INK)
    d.text((col_x[1] + 14, y + 10), b1, font=F_TAB, fill=c1)
    d.text((col_x[2] + 14, y + 10), b2, font=F_TAB, fill=c2)
    y += 40
y += 12
for ln in wrap("结论：标题项是主引擎（唯一能翻盘）；长度项看语料 —— 本 PDF 封面块普遍 60~90 字，-0.5 一次都没触发；先验项两个主题都没改变任何顺序，它是防抖动项，不是排序项。", F_BODY, CONTENT):
    d.text((PAD, y), ln, font=F_BODY, fill=INK)
    y += 30
y += 22

# ---------- ④ 软肋 ----------
y = section("④ 三个软肋（写在卡片上，别等面试官问）", y)
flaws = [
    ("系数是名义值，实际兑现打折",
     "分母是 7 个 token，含「为什么 / 需要 / 进行」三个无信息词 → 单个命中只值 0.14，最好情况 0.29。0.6 的权重实际最多兑现 ≈ 0.17。"),
    ("4/40 块的 section 只是「01 / 02 / 03」",
     "这些块标题项恒为 0，永久吃亏；其中 p008-0（29 字）、p029-0（17 字）还叠 -0.5。章号块本身没用，算是设计，但要承认。"),
    ("严格说不是「标题覆盖率」",
     "分母是 query 的 token 数（主题词有多少落进标题），不是标题自身的 token 数。且 GEO 是所有块共有的词 → 12/20 块都拿到加分，区分度弱。"),
]
for i, (h, body) in enumerate(flaws, 1):
    d.rounded_rectangle([PAD, y, PAD + CONTENT, y + 96], radius=10, fill=AMBER_BG, outline=(228, 199, 152), width=1)
    d.text((PAD + 22, y + 16), f"{i}  {h}", font=F_BODY_BD, fill=AMBER)
    ty = y + 46
    for ln in wrap(body, F_SM, CONTENT - 44):
        d.text((PAD + 22, ty), ln, font=F_SM, fill=INK)
        ty += 26
    y += 96 + 12
y += 10

d.rounded_rectangle([PAD, y, PAD + CONTENT, y + 74], radius=12, fill=TEAL_BG, outline=TEAL, width=2)
d.text((PAD + 26, y + 20), "一句话：重排没有引入新信息，只是用三个先验去修正一个相对分的排序。", font=f(24, True), fill=TEAL)
y += 74 + 52

img = img.crop((0, 0, W, y))
out = Path(__file__).with_name("rerank_formula_card.png")
img.save(out)
print(out, img.size)
