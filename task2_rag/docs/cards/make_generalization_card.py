# -*- coding: utf-8 -*-
"""生成「泛化边界」反思卡片 PNG。数据全部来自实测。"""
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


def f(size, bold=False):
    return ImageFont.truetype(FONT_BD if bold else FONT, size)


F_TITLE = f(42, True)
F_SUB = f(23)
F_SEC = f(28, True)
F_BODY = f(21)
F_BODY_BD = f(21, True)
F_SM = f(19)
F_TAB = f(20)
F_TAB_BD = f(20, True)
F_NUM = f(34, True)


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


img = Image.new("RGB", (W, 2600), (255, 255, 255))
d = ImageDraw.Draw(img)
y = 52

d.text((PAD, y), "泛化边界：为已知主题写的检索，什么时候会失效", font=F_TITLE, fill=INK)
y += 62
d.text((PAD, y), "把「针对这道题」和「通用检索」的差别，用实测数字说清 —— 这不是缺陷，是任务形态决定的取舍", font=F_SUB, fill=INK2)
y += 52


def section(title, y):
    d.rectangle([PAD, y + 3, PAD + 4, y + 31], fill=TEAL)
    d.text((PAD + 16, y), title, font=F_SEC, fill=INK)
    return y + 48


# ---------- ① 定性 ----------
y = section("① 定性：这是编译期优化，不是运行期通用", y)
box_h = 250
gap = 24
bw = (CONTENT - gap) // 2

left_items = [
    "query 是已知常量，可反复改到满意",
    "45 个同义词由人读语料后手写",
    "0 次 LLM 调用，每一步都可解释",
    "代价：换主题就要重写词表",
]
right_items = [
    "query 每次不同，无法预先调参",
    "相似度由 embedding 现场计算",
    "至少 1 次 embedding + 1 次 LLM",
    "优势：换主题零改动，开箱可用",
]

for idx, (head, items, bg, bd, hc) in enumerate([
    ("本项目：构建期优化（实际形态）", left_items, TEAL_BG, TEAL, TEAL),
    ("通用 RAG：运行期检索", right_items, GRAY_BG, GRAY_BD, INK),
]):
    x0 = PAD + idx * (bw + gap)
    d.rounded_rectangle([x0, y, x0 + bw, y + box_h], radius=12, fill=bg, outline=bd, width=2)
    d.text((x0 + 24, y + 22), head, font=F_BODY_BD, fill=hc)
    ty = y + 66
    for it in items:
        d.ellipse([x0 + 26, ty + 9, x0 + 32, ty + 15], fill=hc if hc == TEAL else INK3)
        for ln in wrap(it, F_BODY, bw - 76):
            d.text((x0 + 44, ty), ln, font=F_BODY, fill=INK)
            ty += 30
        ty += 14
y += box_h + 46

# ---------- ② 实测 ----------
y = section("② 实测：手写词表到底买了多少", y)
d.text((PAD, y), "分别只跑原句、再跑五路融合，看最终 top6 里有多少块是靠扩展词表才进的", font=F_BODY, fill=INK2)
y += 40

rows = [
    ("主题一", [0, 1, 2, 3, 4, 5], [1, 4], "p012-0 原句名次 11、p014-0 第 8"),
    ("主题二", [0, 1, 2, 3, 4, 5], [3, 5], "p019-0 原句名次 9、p006-1 第 8"),
]
for label, cells, saved, note in rows:
    d.text((PAD, y + 8), label, font=F_BODY_BD, fill=INK)
    sx = PAD + 84
    for i in cells:
        is_saved = i in saved
        d.rounded_rectangle([sx, y, sx + 34, y + 32], radius=6,
                            fill=TEAL if is_saved else GRAY_BG,
                            outline=TEAL if is_saved else GRAY_BD, width=1)
        if is_saved:
            d.text((sx + 17, y + 5), "扩", font=f(17, True), fill=(255, 255, 255), anchor="ma")
        sx += 40
    d.text((PAD + 84 + 40 * 6 + 16, y + 5), note, font=F_SM, fill=INK2)
    y += 46

d.text((PAD, y + 2), "两个主题都是 2 / 6 —— 词表贡献约 1/3 上下文，另外 4 块靠原句就够了：有用，但不是命门",
       font=F_BODY_BD, fill=TEAL)
y += 56

# ---------- ③ 三种查询 ----------
y = section("③ 换成未知 query：三种输入，三种结局", y)
col_x = [PAD, PAD + 420, PAD + 520, PAD + 980]
col_w = [420, 100, 460, CONTENT - 980]
heads = ["输入类型", "路线数", "实测结果", "判定"]
d.rectangle([PAD, y, PAD + CONTENT, y + 40], fill=(243, 243, 240))
for i, h in enumerate(heads):
    d.text((col_x[i] + 14, y + 10), h, font=F_TAB_BD, fill=INK)
y += 40

trows = [
    ("含表内词（GEO / 出海 / 优化 / 品牌）", "5", "top6 补回 2 块，融合分 3.35", "增益", TEAL, TEAL_BG),
    ("无表内词但含稀有词（「询盘」）", "1", "退化成纯 BM25，top1 正中「询盘 300+」案例\n覆盖率 100%", "不命中也不崩", TEAL, TEAL_BG),
    ("说法与语料不一致（「取代 SEO」）", "2", "覆盖率 40% → 三态判 degrade，降级生成并声明覆盖度", "降级", AMBER, AMBER_BG),
]
for txt, n, res, verdict, vc, vbg in trows:
    res_lines = wrap(res, F_TAB, col_w[2] - 28)
    rh = 20 + 28 * len(res_lines) + 8
    d.line([PAD, y + rh, PAD + CONTENT, y + rh], fill=LINE, width=1)
    d.text((col_x[0] + 14, y + 14), txt, font=F_TAB, fill=INK)
    d.text((col_x[1] + 14, y + 12), n, font=F_NUM, fill=INK2)
    ty = y + 14
    for ln in res_lines:
        d.text((col_x[2] + 14, ty), ln, font=F_TAB, fill=INK)
        ty += 28
    d.rounded_rectangle([col_x[3] + 10, y + 14, col_x[3] + 10 + d.textlength(verdict, font=F_TAB_BD) + 28,
                         y + 46], radius=16, fill=vbg, outline=vc, width=1)
    d.text((col_x[3] + 24, y + 20), verdict, font=F_TAB_BD, fill=vc)
    y += rh + 4

y += 12
for ln in wrap("第三行最该记住：覆盖率按词面算，是通用查询下最大的误伤源 —— 拦得住「客户名单」，也曾错杀换了说法的合法主题（现由 degrade 档接住，见 C1）",
               F_BODY, CONTENT):
    d.text((PAD, y), ln, font=F_BODY, fill=RED)
    y += 30
for ln in wrap("换句话说，手写的不是「同义词」，是「这道题在这份语料里的说法」。它只认见过的说法，不是不会答新问题。",
               F_BODY, CONTENT):
    d.text((PAD, y), ln, font=F_BODY, fill=INK2)
    y += 30
y += 26

# ---------- ④ 分数/覆盖率两道信号 → 三态闸门 ----------
y = section("④ 顺带发现：分数信号对单路线基本失效，覆盖率才是主判据", y)
lines = [
    ("单路线时 fused 是「除以自己的 max」，最高块恒为 1.0", INK),
    ("1.0 → s/(s+1) = 0.5 → 加 0.05 先验 = 0.55，永远高于 0.35 的 SCORE_GATE", INK),
    ("所以真正拦住「客户名单」的是覆盖率 33% < DEGRADE_GATE 0.40 → refuse，不是分数闸门", TEAL),
    ("注：旧注释写「外主题 < 0.2」，实测 top1 = 0.6525 —— guard.py 注释已重写订正（B5/B6）", AMBER),
]
for txt, color in lines:
    for ln in wrap(("· " if color is INK else "→ ") + txt, F_BODY, CONTENT):
        d.text((PAD, y), ln, font=F_BODY, fill=color)
        y += 31
    y += 6
y += 18

# ---------- ⑤ 改哪里 ----------
y = section("⑤ 真要通用，只改一处：词表的来源", y)
for ln in wrap("机制一行不改 —— 多路扩展 → 逐路归一化 → 融合 → 启发式重排 → 三态闸门 全部保留；只把手写的 45 词换成运行时生成：", F_BODY, CONTENT):
    d.text((PAD, y), ln, font=F_BODY, fill=INK)
    y += 31
y += 8
opts = ["LLM 一次调用生成 8~12 条查询变体", "从语料自举 n-gram / 章节标题做候选词表", "并联一路 embedding 检索兜底（标准 hybrid）"]
ox = PAD
for o in opts:
    tw = d.textlength(o, font=F_SM)
    d.rounded_rectangle([ox, y, ox + tw + 32, y + 40], radius=8, fill=GRAY_BG, outline=GRAY_BD, width=1)
    d.text((ox + 16, y + 9), o, font=F_SM, fill=INK)
    ox += tw + 32 + 16
y += 66

d.rounded_rectangle([PAD, y, PAD + CONTENT, y + 76], radius=12, fill=TEAL_BG, outline=TEAL, width=2)
d.text((PAD + 28, y + 22), "一句话：检索机制是通用的，45 个词的映射表是可插拔层 —— 换掉它，架构不变。",
       font=f(24, True), fill=TEAL)
y += 76 + 56

img = img.crop((0, 0, W, y))
out = Path(__file__).with_name("generalization_boundary.png")
img.save(out)
print(out, img.size)
