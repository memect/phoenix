"""
Optimize Agent 示例用法

这个脚本展示了如何使用 OptimizeAgent 进行代码优化。
"""

import asyncio
import logging
from extract_agent.core.langgraph_workflow.optimize_agent import OptimizeAgent, create_optimize_agent
from extract_agent.core.llm.llm import get_llm_by_name
from extract_agent.core.settings.llm_config import Settings
from extract_agent.core.recorder.inmemeory_recorder import InMemoryRecorder

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_optimize_agent():
    """演示 OptimizeAgent 的基本用法"""
    
    print("=== Optimize Agent Demo ===\n")
    
    # 1. 初始化 LLM
    settings = Settings()
    recorder = InMemoryRecorder()
    
    try:
        llm = get_llm_by_name(settings.llm_config, settings.code_llm, recorder)
        print(f"✅ LLM 初始化成功: {settings.code_llm}")
    except Exception as e:
        print(f"❌ LLM 初始化失败: {e}")
        print("使用 Mock LLM 进行演示...")
        # 这里可以创建一个 Mock LLM 用于演示
        return
    
    # 2. 创建 OptimizeAgent
    agent = create_optimize_agent(llm=llm, max_iterations=5)
    print("✅ OptimizeAgent 创建成功\n")
    
    # 3. 运行优化任务
    user_input = """
    请优化当前的代码，目标是将准确率从0.75提升到0.9以上。
    重点关注解析错误和空指针异常问题。
    """
    
    print(f"🚀 开始优化任务...")
    print(f"用户输入: {user_input.strip()}\n")
    
    try:
        # 运行代理
        final_state = await agent.run(
            user_input=user_input.strip(),
            target_accuracy=0.9
        )
        
        print("✅ 优化流程完成！\n")
        
        # 4. 显示结果
        print("📊 最终状态:")
        print(f"  - 总迭代次数: {final_state['iteration_count']}")
        print(f"  - 是否停止: {final_state['should_stop']}")
        print(f"  - 目标准确率: {final_state.get('target_accuracy', 'N/A')}")
        print(f"  - 当前准确率: {final_state.get('current_accuracy', 'N/A')}")
        print(f"  - 消息总数: {len(final_state['messages'])}\n")
        
        # 5. 显示消息历史
        agent.print_message_history(final_state)
        
        # 6. 分析消息类型分布
        messages = final_state['messages']
        message_types = {}
        for msg in messages:
            message_types[msg.type] = message_types.get(msg.type, 0) + 1
        
        print("📈 消息类型分布:")
        for msg_type, count in message_types.items():
            print(f"  - {msg_type}: {count}")
        
    except Exception as e:
        print(f"❌ 优化流程失败: {e}")
        logger.exception("详细错误信息:")


async def demo_with_custom_tools():
    """演示如何使用自定义工具"""
    
    print("\n=== 自定义工具演示 ===\n")
    
    from langchain_core.tools import tool
    
    @tool
    def custom_analysis_tool(data_type: str) -> dict:
        """自定义分析工具"""
        return {
            "analysis_type": data_type,
            "result": f"对 {data_type} 的分析结果",
            "recommendations": ["建议1", "建议2"]
        }
    
    # 这里可以演示如何添加自定义工具
    print("🔧 自定义工具示例:")
    print(f"  工具名: {custom_analysis_tool.name}")
    print(f"  工具描述: {custom_analysis_tool.description}")


if __name__ == "__main__":
    # 运行演示
    asyncio.run(demo_optimize_agent())
    asyncio.run(demo_with_custom_tools())
