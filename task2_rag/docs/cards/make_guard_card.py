# -*- coding: utf-8 -*-
"""生成「幻觉闸门（三态）」说明卡片 PNG。数据来自实测逐词拆解与 14 主题混淆矩阵。"""
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
RED_BG = (253, 240, 240)
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
F_CHIP = f(19)


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


img = Image.new("RGB", (W, 2700), (255, 255, 255))
d = ImageDraw.Draw(img)
y = 52

d.text((PAD, y), "幻觉闸门：不是内容安全审查，是「资料够不够写」", font=F_TITLE, fill=INK)
y += 60
d.text((PAD, y), "三态闸门 normal / degrade / refuse + 3 个实测案例（全部实测，不是示意）", font=F_SUB, fill=INK2)
y += 50


def section(title, y):
    d.rectangle([PAD, y + 3, PAD + 4, y + 31], fill=TEAL)
    d.text((PAD + 16, y), title, font=F_SEC, fill=INK)
    return y + 50


# ---------- ① 纠正 ----------
y = section("① 先纠正：它判的不是「语料对不对」也不是「是不是机密」", y)
bw = (CONTENT - 24) // 2
bh = 232
x0 = PAD
d.rounded_rectangle([x0, y, x0 + bw, y + bh], radius=12, fill=RED_BG, outline=(220, 160, 160), width=2)
d.text((x0 + 22, y + 18), "它不做的事", font=F_BODY_BD, fill=RED)
nots = ["判断语料是否真实、准确、合规", "识别机密 / 商业秘密 / 敏感信息", "任何安全分类器（代码里没有敏感词表）"]
ty = y + 56
for s in nots:
    d.text((x0 + 24, ty), "×", font=F_SM, fill=RED)
    d.text((x0 + 48, ty), s, font=F_SM, fill=INK)
    ty += 30

x1 = PAD + bw + 24
d.rounded_rectangle([x1, y, x1 + bw, y + bh], radius=12, fill=TEAL_BG, outline=TEAL, width=2)
d.text((x1 + 22, y + 18), "它做的事", font=F_BODY_BD, fill=TEAL)
tos = ["主题的核心实词，在 top8 片段里找不找得到证据", "覆盖过低 → refuse；覆盖中等 → degrade 降级 + 文首声明", "这是一道 grounding（接地）闸门，不交给模型自由发挥"]
ty = y + 56
for s in tos:
    d.text((x1 + 24, ty), "√", font=F_SM, fill=TEAL)
    d.text((x1 + 48, ty), s, font=F_SM, fill=INK)
    ty += 30
y += bh + 18
for ln in wrap("「客户名单」被 refuse，不是因为它属于商业秘密，而是因为 PDF 里根本没有客户名单 —— 三态只区分「证据够不够」，不做内容审查。", F_BODY_BD, CONTENT):
    d.text((PAD, y), ln, font=F_BODY_BD, fill=RED)
    y += 30
y += 20

# ---------- ② 三态闸门 ----------
y = section("② 三态判定：按分数与覆盖率分档（C1 修复）", y)
gates = [
    ("refuse 硬拒", "无命中 / 分 < 0.35 / 覆盖 < 0.40 / 来源 < 2 → 输出结构化原因与缺口，不调用 LLM", RED),
    ("degrade 降级", "0.40 ≤ 覆盖 < 0.60 → 照常生成，但文首插入「资料覆盖度说明」，未覆盖部分不作推断", AMBER),
    ("normal 正常", "覆盖 ≥ 0.60 且来源 ≥ 2 → 正常生成，无额外声明", TEAL),
]
gx, gw, gh = PAD, 380, 150
for name, body, color in gates:
    d.rounded_rectangle([gx, y, gx + gw, y + gh], radius=10, fill=GRAY_BG, outline=color, width=2)
    d.text((gx + 16, y + 14), name, font=F_BODY_BD, fill=color)
    ty = y + 52
    for ln in wrap(body, F_SM, gw - 32):
        d.text((gx + 16, ty), ln, font=F_SM, fill=INK)
        ty += 26
    gx += gw + 28
y += gh + 16
for ln in wrap("14 主题混淆矩阵（docs/eval.md）：旧两态 0.35 + 0.60 误拒 2/9、误放 0；三态后误拒 0 / 误放 0，判对 14/14。「证据不完整」与「语料外」不再被当成同一件事。", F_SM, CONTENT):
    d.text((PAD, y), ln, font=F_SM, fill=INK2)
    y += 27
y += 24

# ---------- ③ 覆盖率怎么算 ----------
y = section("③ 覆盖率怎么算：先减料，再匹配", y)
steps = [
    ("1  先剔除三类词", "停用词 + 疑问框架词（为什么 / 需要 / 进行 / 如何）+ 主体词（万悉科技 / trendee，它们必然命中，不提供证据）"),
    ("2  再逐个匹配", "精确子串优先；中文词退一步看前 2 字是否相同（合规性 ≈ 合规）；英文和数字只认精确"),
    ("3  覆盖率 → 三态", "命中数 ÷ 过滤后实词数：< 0.40 refuse；[0.40, 0.60) degrade；≥ 0.60 且来源 ≥ 2 normal"),
]
for head, body in steps:
    d.text((PAD, y), head, font=F_TAB_BD, fill=BLUE)
    ty = y
    for ln in wrap(body, F_SM, CONTENT - 210):
        d.text((PAD + 210, ty), ln, font=F_SM, fill=INK)
        ty += 27
    y = max(ty, y + 34) + 8
y += 20

# ---------- ④ 三个案例 ----------
y = section("④ 三个案例：逐词看谁命中、谁落空", y)


def chips(items, y, note_lines):
    cx = PAD
    for word, status in items:
        if status == "hit":
            bg, bd, fg, mark = TEAL_BG, TEAL, TEAL, "√"
        elif status == "miss":
            bg, bd, fg, mark = RED_BG, (220, 160, 160), RED, "×"
        else:
            bg, bd, fg, mark = GRAY_BG, GRAY_BD, INK3, "—"
        txt = f"{word} {mark}"
        w_ = d.textlength(txt, font=F_CHIP) + 30
        d.rounded_rectangle([cx, y, cx + w_, y + 40], radius=8, fill=bg, outline=bd, width=1)
        d.text((cx + 15, y + 9), txt, font=F_CHIP, fill=fg)
        cx += w_ + 10
    y += 54
    for ln in note_lines:
        d.text((PAD, y), ln, font=F_SM, fill=INK2)
        y += 27
    return y + 18


d.text((PAD, y), "案例 A｜万悉科技的客户名单和融资历史 → refuse", font=F_BODY_BD, fill=RED)
y += 36
y = chips([("万悉科技", "skip"), ("客户名单", "miss"), ("融资", "miss"), ("历史", "hit")], y,
          ["原始 4 个 token，「万悉科技」作为主体词先被剔除 → 只剩 3 个：1 命中 / 3 = 33% < 0.40 → refuse",
           "注意那个 √ 是假的：「历史」命中的是语料里「历史最快 移动爆款」那一句，跟「融资历史」毫无关系"])
y += 14

d.text((PAD, y), "案例 B｜AI 搜索会不会取代 SEO → degrade（旧两态在这里误拒）", font=F_BODY_BD, fill=AMBER)
y += 36
y = chips([("ai", "hit"), ("搜索", "hit"), ("不会", "miss"), ("取代", "miss"), ("seo", "miss")], y,
          ["2 命中 / 5 = 40% → 旧版 0.60 闸门硬拒（误伤）；三态落入 [0.40, 0.60) degrade",
           "现在照常生成，但文首声明「本次检索只覆盖主题词 40%……未覆盖部分不作推断」"])
y += 14

d.text((PAD, y), "案例 C｜生成式引擎优化和传统 SEO 的区别 → degrade", font=F_BODY_BD, fill=AMBER)
y += 36
y = chips([("生成式", "hit"), ("引擎", "miss"), ("优化", "hit"), ("传统", "miss"), ("seo", "hit"), ("区别", "miss")], y,
          ["3 命中 / 6 = 50% → degrade；top1 0.641、6 个命中来源，证据够写但说法与语料不完全一致",
           "这正是旧两态误拒的第 2 条，三态把它接住，同时不编造未覆盖部分"])
y += 10

# ---------- ⑤ 成本 ----------
y = section("⑤ 放在生成之前的账", y)
for ln in wrap("refuse 省一次注定失败的 LLM 调用。更本质的是：判定必须是系统行为 —— 模型的「我不知道」不可控，系统的 refuse / degrade 是确定性输出，且 degrade 的声明让覆盖度可见。", F_BODY, CONTENT):
    d.text((PAD, y), ln, font=F_BODY, fill=INK)
    y += 30
for ln in wrap("顺序上它排在 build_context 之后（上下文已拼好才判），但拼字符串是微秒级，不值得为此调整流水线。", F_SM, CONTENT):
    d.text((PAD, y), ln, font=F_SM, fill=INK2)
    y += 27
y += 34

d.rounded_rectangle([PAD, y, PAD + CONTENT, y + 74], radius=12, fill=TEAL_BG, outline=TEAL, width=2)
d.text((PAD + 26, y + 20), "一句话：闸门不问「这话能不能说」，只问「资料里有没有依据」；证据不足就降级声明，而不是一律拒答。",
       font=f(24, True), fill=TEAL)
y += 74 + 52

img = img.crop((0, 0, W, y))
out = Path(__file__).with_name("guard_card.png")
img.save(out)
print(out, img.size)
