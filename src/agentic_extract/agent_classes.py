"""
Agent 类封装

将 Supervisor、BusinessAgent、DevAgent 封装为类，
便于依赖注入和方法调用。
未定义的属性/方法自动代理到内部 ReActAgent。

当 agent 到达 max_iters 限制时，返回消息的 metadata 中
会标记 _max_iters_reached=True，供调用方检测。
"""

import logging

from agentscope.agent import ReActAgent
from agentscope.message import Msg

logger = logging.getLogger(__name__)


async def _call_with_max_iters_detection(agent: ReActAgent, msg: Msg, **kwargs) -> Msg:
    """调用 agent 并检测是否到达 max_iters 限制。

    通过比较调用前后的 memory size，判断是否跑满了 max_iters 轮。
    每轮 reasoning-acting 至少增加 2 条消息（assistant + tool_result），
    所以 memory 增量 >= max_iters * 2 说明循环跑满。
    """
    mem_before = (await agent.memory.size()) if agent.memory else 0
    resp = await agent(msg, **kwargs)
    mem_after = (await agent.memory.size()) if agent.memory else 0

    mem_delta = mem_after - mem_before
    # 每轮至少 2 条（reasoning + tool_result），跑满 max_iters 轮
    if mem_delta >= agent.max_iters * 2:
        logger.warning(
            "%s 到达 max_iters=%d 限制 (memory 增量 %d)",
            agent.name, agent.max_iters, mem_delta,
        )
        if resp.metadata is None:
            resp.metadata = {}
        if isinstance(resp.metadata, dict):
            resp.metadata["_max_iters_reached"] = True

    return resp


class Supervisor:
    """Supervisor Agent 封装"""

    def __init__(self, agent: ReActAgent):
        self.agent = agent

    def __getattr__(self, name):
        return getattr(self.agent, name)

    async def __call__(self, msg: Msg, **kwargs) -> Msg:
        return await _call_with_max_iters_detection(self.agent, msg, **kwargs)


class BusinessAgent:
    """BusinessAgent 封装"""

    def __init__(self, agent: ReActAgent):
        self.agent = agent

    def __getattr__(self, name):
        return getattr(self.agent, name)

    async def __call__(self, msg: Msg, **kwargs) -> Msg:
        return await _call_with_max_iters_detection(self.agent, msg, **kwargs)

    async def answer_question(self, question: str, context: str | None = None) -> str:
        """回答 DevAgent 的业务问题

        Args:
            question: 问题内容
            context: 可选的上下文信息

        Returns:
            回答文本
        """
        content_parts = [f"DevAgent 询问: {question}"]
        if context:
            content_parts.append(f"\n上下文: {context}")

        msg = Msg(
            name="user",
            content="".join(content_parts),
            role="user",
        )

        response = await self.agent(msg)
        return response.get_text_content()


class DevAgent:
    """DevAgent 封装"""

    def __init__(self, agent: ReActAgent, business_agent: "BusinessAgent | None" = None):
        self.agent = agent
        self.business_agent = business_agent

        if business_agent:
            self._register_ask_business_tool()

    def __getattr__(self, name):
        return getattr(self.agent, name)

    async def __call__(self, msg: Msg, **kwargs) -> Msg:
        return await _call_with_max_iters_detection(self.agent, msg, **kwargs)

    def _register_ask_business_tool(self):
        """注册 ask_business_agent 工具"""
        from agentscope.tool import ToolResponse
        from agentscope.message import TextBlock

        business_agent = self.business_agent

        async def ask_business_agent(question: str, context: str = "") -> ToolResponse:
            """向 BusinessAgent 询问业务相关问题

            当你遇到以下情况时，可以使用此工具：
            - 不理解某个字段的业务含义
            - 需要了解数据的业务背景
            - 想知道某种数据模式是否正常
            - 需要业务层面的提取策略建议

            Args:
                question: 你的问题，要具体清晰
                context: 可选的上下文信息，如当前处理的文档ID、遇到的具体数据等

            Returns:
                ToolResponse 包含 BusinessAgent 的回答
            """
            if business_agent is None:
                return ToolResponse(
                    content=[TextBlock(type="text", text="错误：BusinessAgent 未初始化")]
                )

            try:
                answer = await business_agent.answer_question(
                    question=question,
                    context=context if context else None,
                )
                return ToolResponse(
                    content=[TextBlock(type="text", text=answer)]
                )
            except Exception as e:
                return ToolResponse(
                    content=[TextBlock(type="text", text=f"调用 BusinessAgent 时出错: {e}")]
                )

        self.agent.toolkit.register_tool_function(ask_business_agent)
