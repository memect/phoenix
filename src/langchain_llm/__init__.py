"""
LangChain LLM Module

LLM 客户端封装模块，提供：
- get_llm_client(): 获取 LLM 客户端
- get_llm_client_by_model(): 根据模型名称获取 LLM 客户端
- LLM: LLM 配置类
"""

from .llm import get_llm_client, LLM, get_llm_client_by_model

__all__ = [
    "get_llm_client",
    "LLM",
    "get_llm_client_by_model"
]