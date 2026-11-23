"""标题归一化与 maxi dress 三段式打标（可解释规则编号 R1~R6）。

题面只给了 7 类写法（大小写/连字符/多空格/词序/所有格等），但线上标题的分布远比
题面宽：组合词（`MaxiDress`）、斜杠分隔（`Maxi/Dress`）、复数（`Maxi Dresses`）、
拼写误差（`Maxy Dress`/`Maxi Dres`）、属性词混入（`Midi Length`/`Mini Print`）、
型号编号（`A12`/`No.2001`）、同 ID 冲突标题。本模块的处理顺序是固定的，每一步
都能单独解释、单独测试：

  1) 归一化（NFKC 全角→半角、小写、所有格、分隔符统一、压缩空白）
  2) 词级重建（复数还原 → 组合词按词表贪心切分 → 已知拼写变体纠错）
  3) 档位判定（R1~R6），属性词不算档位，档位冲突进灰区

规则（Python 为权威口径，sql/02_dwd_tag.sql 是可交叉验证的 SQL 版）：

  归一化：小写 → 所有格撇号转空格（women's → women s）→ 分隔符（- _ / | ;）转空格
          → 压缩连续空格 → 复数还原（dresses → dress）→ 组合词切分（maxidress → maxi dress）
  纠错：maxi/dress/mini/midi/long/skirt 做 Damerau-Levenshtein ≤1 的变体映射，
        但先剔除已知同形英文词（maxim/maximum/address…），避免 Maxim Dress 被纠成 maxi dress
  R1 主档位含 mini/midi（且不是属性修饰）                      → excluded
  R2 含 maxi 但无 dress（maxi skirt 等）                       → excluded
  R3 含 maxi 且含 dress                                       → core
  R4 含 dress 且含 long、无 maxi                              → gray_zone
  R5 其余                                                     → excluded
  R6 档位冲突（mini/midi 与 maxi 同时作为主档位）              → gray_zone（需人工确认）

「属性词不算档位」是本版的关键修正：`Maxi Dress Midi Length`（中长款属性）与
`Maxi Dress Mini Print`（迷你印花）里的 midi/mini 是修饰语而不是长度档位，旧版
无条件优先 R1 会把它们误杀成 excluded——那是**口径污染**（趋势图里少了一部分
真实 maxi dress 的销量），比"漏一个商品"严重。属性词表见 _ATTR_AFTER，按"紧邻
后一个词"判定，不做全局包含判断（否则 `Mini Dress Print` 里的 mini 也会被放过）。

R6 把"说不清"的样本显式送进灰区并标记，而不是沉默丢弃：灰区可开关、可审计，
`dim_product.tag_rule` 能逐条回查为什么被这样判。

tag_product() 返回 (tag_status, rule_id)，rule_id 落 dim_product.tag_rule；
tag_title() 是保留的薄封装，既有测试与下游导入不受影响。
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

_RE_APOSTROPHE = re.compile(r"(\w+)'s")
_RE_SEPARATORS = re.compile(r"[-_/|;\s]+")

CORE = "core"
GRAY_ZONE = "gray_zone"
EXCLUDED = "excluded"

# 词表：只放打标判定真正需要的核心词（含复数/屈折形由 _deplural 处理）
_LEX = {"maxi", "midi", "mini", "long", "dress", "skirt"}

# 拼写容错的目标词（不做全词表纠错，避免把正常英文词纠成档位词）
_FUZZY_TARGETS = ("maxi", "dress", "mini", "midi", "long", "skirt")

# 已知同形词黑名单：这些词与档位词编辑距离 ≤1，但不是档位词，纠错前先挡掉。
# 不加这层，`Maxim Dress`（格言/品牌名）会被纠成 `maxi dress` 而误判为 core。
_FUZZY_BLOCK = {
    "maxim", "maxima", "maximum", "maxis",
    "address", "redress", "undress", "dresser", "dressing", "dressed",
    "longs", "minis", "skirted",
}

# 属性词：紧跟 mini/midi 时说明它是修饰语（迷你印花 / 中长款），不是长度档位
_ATTR_AFTER = {
    "print", "prints", "length", "sleeve", "sleeves", "hem", "cut", "pleat", "pleats",
    "slit", "waist", "fit", "rise", "size", "petite", "pattern", "floral", "dot", "dots",
    "stripe", "stripes", "logo", "neck", "collar", "button", "buttons", "pocket", "pockets",
    "belt", "tie", "trim", "detail", "details", "panel", "yoke", "ruffle", "ruffles",
    "edition", "series", "collection", "line",
}


def _deplural(tok: str) -> str:
    """只对已知词做规则化复数还原，不引重型 stemmer（避免把 address 变成 addres）。"""
    if tok in _LEX:
        return tok
    if tok.endswith("es") and tok[:-2] in _LEX:
        return tok[:-2]
    if tok.endswith("s") and len(tok) > 2 and tok[:-1] in _LEX:
        return tok[:-1]
    return tok


def _dl1(a: str, b: str) -> bool:
    """Damerau-Levenshtein 距离是否 ≤1（含相邻字符换位）。"""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diff = [i for i in range(la) if a[i] != b[i]]
        if len(diff) == 1:
            return True
        # 换位（dres s -> dres?）：仅两个相邻位置互换
        return len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]
    short, long_ = (a, b) if la < lb else (b, a)
    i = 0
    while i < len(short) and short[i] == long_[i]:
        i += 1
    return short[i:] == long_[i + 1:]


def _segment(tok: str) -> list[str]:
    """把组合词按词表贪心切分；无法完全切分时原样返回（避免误拆普通单词）。"""
    if tok in _LEX:
        return [tok]
    out: list[str] = []
    i = 0
    while i < len(tok):
        for length in range(min(7, len(tok) - i), 1, -1):
            piece = _deplural(tok[i:i + length])
            if piece in _LEX:
                out.append(piece)
                i += length
                break
        else:
            return [tok]
    return out


def _canon_words(tokens: list[str]) -> list[str]:
    """词级重建：复数还原 → 组合词切分 → 拼写变体纠错。顺序不可换。"""
    out: list[str] = []
    for raw in tokens:
        for piece in _segment(_deplural(raw)):
            if piece in _LEX:
                out.append(piece)
                continue
            if piece in _FUZZY_BLOCK or len(piece) < 4:
                out.append(piece)
                continue
            hit = next((t for t in _FUZZY_TARGETS if _dl1(piece, t)), None)
            out.append(hit or piece)
    return out


def normalize_title(raw: str) -> str:
    """归一化标题：NFKC、小写、所有格、分隔符统一、压缩空白。"""
    s = unicodedata.normalize("NFKC", str(raw)).strip().lower()
    s = _RE_APOSTROPHE.sub(r"\1 s", s)
    s = _RE_SEPARATORS.sub(" ", s)
    return s.strip()


def parse_title(raw: str) -> tuple[str, list[str]]:
    """归一化 + 词级重建，返回 (title_norm, words)。words 已含复数/组合/拼写纠错。"""
    norm = normalize_title(raw)
    return norm, _canon_words(norm.split())


def tag_product(title_norm: str) -> tuple[str, str]:
    """词级三段式判定，返回 (tag_status, rule_id)。规则编号固定 R1~R6。

    入参要求是 normalize_title() 的产物；若传入原始标题，内部会再做一次解析，
    保证调用方不需要记住"必须先归一化"。
    """
    norm, words = parse_title(title_norm)
    _ = norm
    wset = set(words)
    has_maxi = "maxi" in wset
    has_dress = "dress" in wset

    # 只看"紧跟属性词"的 mini/midi 是否为主档位
    tier_hits = [
        w for i, w in enumerate(words)
        if w in ("mini", "midi") and not (i + 1 < len(words) and words[i + 1] in _ATTR_AFTER)
    ]
    if tier_hits and has_maxi:
        return GRAY_ZONE, "R6"          # 档位信号互相矛盾：进灰区并标记，不静默丢弃
    if tier_hits:
        return EXCLUDED, "R1"
    if has_maxi and not has_dress:
        return EXCLUDED, "R2"
    if has_maxi and has_dress:
        return CORE, "R3"
    if has_dress and ("long" in wset or {"floor", "length"} <= wset):
        return GRAY_ZONE, "R4"      # long dress / floor length dress 同属长款灰区
    return EXCLUDED, "R5"


def tag_title(title_norm: str) -> str:
    """薄封装：只取 tag_product() 的档位，保持既有导入与测试不变。"""
    return tag_product(title_norm)[0]


def row_hash(row: dict) -> str:
    """幂等键：md5(7 个业务字段按固定顺序拼接)。

    product_id + title_norm + sales_count + dt_utc + user_id + category + platform
    完全相同的输入 → 相同 hash → 落库前被 anti-join 过滤，重跑不增行。
    """
    payload = "|".join(
        str(row[k])
        for k in ("product_id", "title_norm", "sales_count", "dt_utc", "user_id", "category", "platform")
    )
    return hashlib.md5(payload.encode("utf-8")).hexdigest()
