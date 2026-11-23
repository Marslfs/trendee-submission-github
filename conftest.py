# -*- coding: utf-8 -*-
"""根级 pytest 配置补充：解决两个子项目「顶层包同名 src」的冲突。

pytest.ini 的 pythonpath 把 task1_data_api 与 task2_rag 同时加进 sys.path，
但两者都有常规包 src/（带 __init__.py）——Python 只会缓存先导入的那一个，
导致后收集的测试 import src.xxx 找不到模块（实测 2 个 collection error）。

这里在收集前把 src 换成一个 __path__ 覆盖两个目录的命名空间包，
src.normalize / src.api / src.guard / src.rerank 都能各自解析，互不干扰。
子目录单独跑 pytest 时本文件仍会被加载，行为一致。
"""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_PATHS = [str(ROOT / "task1_data_api" / "src"), str(ROOT / "task2_rag" / "src")]

_pkg = sys.modules.get("src")
if _pkg is None or not hasattr(_pkg, "__path__") or len(list(_pkg.__path__)) < 2:
    _pkg = types.ModuleType("src")
    _pkg.__path__ = _PATHS
    _pkg.__package__ = "src"
    sys.modules["src"] = _pkg
