"""
Memect API Server Module

API 服务模块，提供：
- Api: API 客户端类
- get_docjson(): 获取 DocJSON 数据
- set_cache_dir(): 设置缓存目录
"""

from .apiserver import Api
from .parse import get_docjson, set_cache_dir

__all__ = ['Api', 'get_docjson', 'set_cache_dir']   