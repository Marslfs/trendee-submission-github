"""标题归一化与 maxi dress 三段式打标。

规则（与 sql/02_tag.sql 交叉验证，Python 版为准）：
  归一化：小写 → 所有格撇号转空格（women's → women s）→ 连字符转空格 → 压缩连续空格
  core     : 归一化后同时含 maxi 与 dress，且不含 mini/midi
  excluded : 含 mini/midi（长度档位冲突）；或含 maxi 但无 dress（maxi skirt ≠ maxi dress）
  gray_zone: 含 dress + long 但无 maxi —— 计入但打标，API 可按 include_gray_zone 开关
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

_RE_APOSTROPHE = re.compile(r"(\w+)'s")
_RE_SEPARATORS = re.compile(r"[-_\s]+")

CORE = "core"
GRAY_ZONE = "gray_zone"
EXCLUDED = "excluded"


def normalize_title(raw: str) -> str:
    """归一化标题：小写、去所有格、连字符/下划线转空格、压连续空白。"""
    s = unicodedata.normalize("NFKC", str(raw)).strip().lower()
    s = _RE_APOSTROPHE.sub(r"\1 s", s)
    s = _RE_SEPARATORS.sub(" ", s)
    return s.strip()


def tag_title(title_norm: str) -> str:
    """三段式判定，返回 core / gray_zone / excluded。"""
    t = title_norm
    words = set(t.split())
    if "mini" in words or "midi" in words:
        return EXCLUDED
    if "maxi" in words and "dress" in words:
        return CORE
    if "maxi" in words:  # maxi skirt / maxi dress 复合词中 dress 缺失
        return EXCLUDED
    if "dress" in words and "long" in words:
        return GRAY_ZONE
    return EXCLUDED


def row_hash(row: dict) -> str:
    """幂等键：md5(全部业务字段按固定顺序拼接)。

    product_id + title_norm + sales_count + dt_utc + user_id + category + platform
    完全相同的输入 → 相同 hash → 落库前被 anti-join 过滤，重跑不增行。
    """
    payload = "|".join(
        str(row[k])
        for k in ("product_id", "title_norm", "sales_count", "dt_utc", "user_id", "category", "platform")
    )
    return hashlib.md5(payload.encode("utf-8")).hexdigest()
