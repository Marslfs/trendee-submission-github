"""进程内 TTL + LRU 缓存（cachetools）。

取舍（面试可讲）：demo 规模用进程内缓存零运维；生产换 Redis，
key 设计不变（trend:{start}:{end}:{platforms}:{gray}），只换实现。
"""
from __future__ import annotations

import functools
import hashlib
import json
from collections.abc import Callable

from cachetools import TTLCache

# 命中区间查询的合理配置：容量 1024 个结果集，TTL 60s
_cache: TTLCache = TTLCache(maxsize=1024, ttl=60)


def make_key(prefix: str, params: dict) -> str:
    """稳定 key：参数按 json 排序序列化后 md5。"""
    payload = json.dumps(params, sort_keys=True, ensure_ascii=False)
    digest = hashlib.md5(payload.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def ttl_cache(prefix: str) -> Callable:
    def decorator(fn: Callable):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = make_key(prefix, {"args": args, "kwargs": kwargs})
            if key in _cache:
                return _cache[key], True
            result = fn(*args, **kwargs)
            _cache[key] = result
            return result, False
        return wrapper
    return decorator


def cache_stats() -> dict:
    return {"entries": len(_cache), "maxsize": _cache.maxsize, "ttl": _cache.ttl}
