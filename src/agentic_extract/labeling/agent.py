"""
LabelingAgent

单文档标注 Agent，负责阅读一篇文档并生成标注数据。
每次调用创建独立的 ReActAgent 实例，避免状态污染。
"""

import json
import logging
from pathlib import Path

from agentscope.message import Msg

logger = logging.getLogger(__name__)
from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.tool import Toolkit, execute_shell_command, view_text_file

from . import prompts as labeling_prompts


class LabelingAgent:
    """单文档标注 Agent

    职责：读取一篇文档，根据 schema 和业务指导生成标注数据。
    """

    def __init__(
        self,
        model: str,
        api_base: str,
        api_key: str,
        timeout: float = 300.0,
        max_retries: int = 0,
    ):
        self._model = model
        self._api_base = api_base
        self._api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries

    async def label_document(
        self,
        doc_id: str,
        schema_json: str,
        business_guide: str,
        docjson_path: str,
    ) -> bool:
        """标注单个文档

        Args:
            doc_id: 文档 ID
            schema_json: schema 定义 JSON 字符串
            business_guide: 业务指导文档内容
            docjson_path: docjson 文件路径

        Returns:
            True 标注成功，False 标注失败
        """
        from ..model_factory import create_model
        from ..tools import register_file_tools

        toolkit = Toolkit()
        toolkit.register_tool_function(execute_shell_command)
        toolkit.register_tool_function(view_text_file)
        register_file_tools(toolkit)

        llm, formatter = create_model(
            model_spec=self._model,
            api_base=self._api_base,
            api_key=self._api_key,
            stream=False,
            timeout=self._timeout,
            max_retries=self._max_retries,
        )

        agent = ReActAgent(
            name=f"LabelingAgent-{doc_id[:8]}",
            sys_prompt=labeling_prompts.SYSTEM_PROMPT,
            model=llm,
            formatter=formatter,
            toolkit=toolkit,
            memory=InMemoryMemory(),
            max_iters=20,
        )

        content = labeling_prompts.build_label_message(
            doc_id=doc_id,
            schema_json=schema_json,
            business_guide=business_guide,
            docjson_path=docjson_path,
        )
        msg = Msg(name="user", content=content, role="user")

        try:
            await agent(msg)
            return True
        except Exception as e:
            logger.warning("文档 %s 标注失败: %s", doc_id, e)
            return False
