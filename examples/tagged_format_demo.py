"""
标签格式工具调用功能演示

本演示展示如何使用标签格式工具调用，避免复杂字符串参数的转义问题。
"""

import asyncio
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nopagent.react_agent import create_tagged_react_agent, ToolCallConfig, ReactAgent


@tool
def search(query: str, limit: int = 5) -> str:
    """搜索工具 - 根据查询搜索信息"""
    return f"搜索结果：找到关于 '{query}' 的 {limit} 条相关信息"


@tool
def write_file(filename: str, content: str, format: str = "text") -> str:
    """写文件工具 - 将内容写入文件"""
    print(f"写入文件 {filename} ({format} 格式):")
    print(f"内容:\n{content}")
    return f"文件 {filename} 写入成功"


@tool
def calculate(x: float, y: float, operation: str = "add") -> str:
    """计算工具 - 执行数学运算"""
    if operation == "add":
        result = x + y
    elif operation == "multiply":
        result = x * y
    elif operation == "subtract":
        result = x - y
    elif operation == "divide":
        result = x / y if y != 0 else "错误：除零"
    else:
        result = "错误：不支持的操作"
    
    return f"计算结果: {x} {operation} {y} = {result}"


async def demo_call_direct_format():
    """演示 call_direct 格式"""
    print("=== 演示 call_direct 格式 ===")
    
    # 创建 LLM（需要配置 API 密钥）
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    # 创建标签格式 ReactAgent
    agent = create_tagged_react_agent(
        llm=llm,
        tools=[search, write_file, calculate],
        format_style="call_direct",
        processing_mode="priority"
    )
    
    # 测试用例
    user_input = """请帮我：
1. 搜索"人工智能发展历程"相关信息
2. 写一个包含复杂文本的报告文件
3. 计算 15.5 + 28.3"""
    
    print(f"用户输入: {user_input}")
    print("\n开始处理...")
    
    try:
        result = await agent.run(user_input)
        
        print(f"\n执行结果:")
        print(f"成功: {result.success}")
        print(f"最终消息: {result.final_message}")
        print(f"执行时间: {result.execution_time:.2f}s")
        
        # 打印执行历史
        agent.print_message_history(result)
        
    except Exception as e:
        print(f"执行失败: {e}")


async def demo_tool_call_param_format():
    """演示 tool_call_param 格式"""
    print("=== 演示 tool_call_param 格式 ===")
    
    # 创建 LLM
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    # 创建标签格式 ReactAgent
    agent = create_tagged_react_agent(
        llm=llm,
        tools=[search, calculate],
        format_style="tool_call_param",
        processing_mode="exclusive"
    )
    
    user_input = "搜索 AI 相关信息，然后计算 100 除以 4"
    
    print(f"用户输入: {user_input}")
    print("\n开始处理...")
    
    try:
        result = await agent.run(user_input)
        
        print(f"\n执行结果:")
        print(f"成功: {result.success}")
        print(f"最终消息: {result.final_message}")
        print(f"执行时间: {result.execution_time:.2f}s")
        
        # 打印执行历史
        agent.print_message_history(result)
        
    except Exception as e:
        print(f"执行失败: {e}")


async def demo_mixed_mode():
    """演示混合模式（同时支持函数调用和标签调用）"""
    print("=== 演示混合模式 ===")
    
    # 创建 LLM
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    # 创建支持混合模式的 ReactAgent
    config = ToolCallConfig(
        format_style="call_direct",
        enable_function_calling=True,
        enable_tagged_calling=True,
        processing_mode="merged"  # 合并处理模式
    )
    
    agent = ReactAgent(
        llm=llm,
        tools=[search, write_file],
        tool_call_config=config
    )
    
    user_input = "搜索一些技术信息，然后创建一个包含长文本的技术文档"
    
    print(f"用户输入: {user_input}")
    print("\n开始处理...")
    
    try:
        result = await agent.run(user_input)
        
        print(f"\n执行结果:")
        print(f"成功: {result.success}")
        print(f"最终消息: {result.final_message}")
        print(f"执行时间: {result.execution_time:.2f}s")
        
        # 打印执行历史
        agent.print_message_history(result)
        
    except Exception as e:
        print(f"执行失败: {e}")


def demo_system_prompt():
    """演示标签格式系统提示"""
    print("=== 演示标签格式系统提示 ===")
    
    # 创建配置
    config = ToolCallConfig(format_style="call_direct")
    
    # 直接使用模板创建系统提示
    from nopagent.react_agent.tagged_format import get_tagged_format_system_prompt
    
    tools = [search, write_file, calculate]
    prompt = get_tagged_format_system_prompt(tools, config, "你是一个智能助手。")
    
    print("生成的 call_direct 格式系统提示：")
    print("=" * 50)
    print(prompt)
    print("=" * 50)
    
    print("\n")
    
    # 演示 tool_call_param 格式
    config2 = ToolCallConfig(format_style="tool_call_param")
    prompt2 = get_tagged_format_system_prompt(tools, config2, "你是一个智能助手。")
    
    print("生成的 tool_call_param 格式系统提示：")
    print("=" * 50)
    print(prompt2)
    print("=" * 50)


async def main():
    """主函数"""
    print("标签格式工具调用功能演示")
    print("=" * 50)
    
    # 演示系统提示
    demo_system_prompt()
    
    print("\n")
    
    # 检查是否配置了 OpenAI API 密钥
    try:
        import os
        if not os.getenv("OPENAI_API_KEY"):
            print("警告: 未设置 OPENAI_API_KEY 环境变量")
            print("请设置后再运行实际的 LLM 演示")
            return
        
        # 演示 call_direct 格式
        await demo_call_direct_format()
        
        print("\n" + "=" * 50 + "\n")
        
        # 演示 tool_call_param 格式
        await demo_tool_call_param_format()
        
        print("\n" + "=" * 50 + "\n")
        
        # 演示混合模式
        await demo_mixed_mode()
        
    except Exception as e:
        print(f"演示过程中出错: {e}")
        print("这可能是因为缺少 OpenAI API 密钥或网络连接问题")


if __name__ == "__main__":
    asyncio.run(main())