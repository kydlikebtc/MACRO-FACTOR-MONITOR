"""
依赖注入 - 提供 DB 和 Swarm 单例
"""
import os
import sys

# 将上层目录加入 Python 路径，以便 import 现有模块
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from db import MacroFactorDB

_db_instance: MacroFactorDB | None = None


def get_db() -> MacroFactorDB:
    """获取 DB 单例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = MacroFactorDB()
    return _db_instance


def get_fred_api_key() -> str | None:
    """从环境变量获取 FRED API Key"""
    return os.environ.get("FRED_API_KEY")
