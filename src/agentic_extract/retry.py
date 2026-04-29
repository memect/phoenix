"""
模型请求重试包装器

开启重试时自动关闭 stream，使用 tenacity 实现指数退避重试。
主要处理 httpx.RemoteProtocolError（stream 中途断开）等网络异常。
"""

from typing import Any

import httpx
import openai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import logging

from agentscope.model import ChatResponse

logger = logging.getLogger(__name__)


# 需要重试的异常类型
# OpenAI SDK 会把底层 httpx 异常包装成自己的异常，两层都需要覆盖
RETRYABLE_EXCEPTIONS = (
    httpx.RemoteProtocolError,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    openai.APIConnectionError,
    openai.APITimeoutError,
)


class RetryModelWrapper:
    """模型重试包装器

    包装 agentscope 的模型对象，在 __call__ 时自动重试。
    使用此包装器时，模型的 stream 必须为 False。
    """

    def __init__(self, model: Any, max_retries: int = 3):
        """
        Args:
            model: agentscope 模型对象（stream 应为 False）
            max_retries: 最大重试次数（不含首次请求）
        """
        self._model = model
        self._max_retries = max_retries

        # 复制原模型的属性
        self.model_name = model.model_name
        self.stream = model.stream

        # 动态创建带重试的调用方法
        self._call_with_retry = retry(
            stop=stop_after_attempt(max_retries + 1),  # +1 包含首次请求
            wait=wait_exponential(multiplier=1, min=1, max=16),
            retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
            before_sleep=self._log_retry,
            reraise=True,
        )(self._do_call)

    def __getattr__(self, name: str) -> Any:
        """代理其他属性访问到原模型"""
        return getattr(self._model, name)

    @staticmethod
    def _log_retry(retry_state) -> None:
        """重试前打印日志"""
        exc = retry_state.outcome.exception()
        attempt = retry_state.attempt_number
        wait = retry_state.next_action.sleep if retry_state.next_action else 0
        logger.warning(
            "请求失败 (attempt %d): %s: %s, %.1fs 后重试",
            attempt, type(exc).__name__, exc, wait,
        )

    async def _do_call(self, *args: Any, **kwargs: Any) -> ChatResponse:
        """实际调用模型"""
        return await self._model(*args, **kwargs)

    async def __call__(self, *args: Any, **kwargs: Any) -> ChatResponse:
        """拦截模型调用，带重试"""
        return await self._call_with_retry(*args, **kwargs)
