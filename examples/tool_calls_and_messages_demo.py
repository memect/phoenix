#!/usr/bin/env python3
"""
tool_calls_and_messages 功能演示
展示解析器如何按顺序记录工具调用和消息
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nopagent.react_agent.parsers import TaggedCallParser, ToolCallConfig
from nopagent.react_agent.models import TaggedToolCall


def demo_tool_calls_and_messages():
    """演示 tool_calls_and_messages 功能"""
    print("🔧 tool_calls_and_messages 功能演示")
    print("=" * 50)
    
    # 创建解析器配置
    config = ToolCallConfig(format_style="call_direct")
    parser = TaggedCallParser(config)
    
    # 示例内容：包含文本和工具调用的混合内容
    content = """我来搜索相关信息。

<call tool="search_documents">
<query>人工智能的发展历史</query>
<limit>3</limit>
</call>

根据搜索结果，我会为您整理信息。

<call tool="analyze_code">
<code>def hello():
    print("Hello World")
    return True</code>
<check_syntax>true</check_syntax>
</call>

分析完成，现在生成报告。"""
    
    print("📝 原始内容:")
    print(content)
    print("\n" + "=" * 50)
    
    # 解析内容
    result = parser.parse_message(content)
    
    print("🔍 解析结果 (按顺序):")
    for i, item in enumerate(result):
        if isinstance(item, str):
            print(f"{i+1}. 📄 文本: {repr(item)}")
        elif isinstance(item, TaggedToolCall):
            print(f"{i+1}. 🔧 工具调用: {item.tool_name}")
            print(f"   参数: {item.args}")
            print(f"   ID: {item.id}")
    
    print("\n" + "=" * 50)
    
    # 分别提取工具调用和文本
    tool_calls = [item for item in result if isinstance(item, TaggedToolCall)]
    text_parts = [item for item in result if isinstance(item, str)]
    
    print("📊 统计信息:")
    print(f"- 总项目数: {len(result)}")
    print(f"- 文本片段数: {len(text_parts)}")
    print(f"- 工具调用数: {len(tool_calls)}")
    
    print("\n📋 工具调用列表:")
    for i, call in enumerate(tool_calls):
        print(f"{i+1}. {call.tool_name} (ID: {call.id})")
        for param_name, param_value in call.args.items():
            print(f"   - {param_name}: {repr(param_value)}")
    
    print("\n📄 文本片段列表:")
    for i, text in enumerate(text_parts):
        print(f"{i+1}. {repr(text)}")


def demo_tool_call_param_format():
    """演示 tool_call_param 格式"""
    print("\n\n🔧 tool_call_param 格式演示")
    print("=" * 50)
    
    config = ToolCallConfig(format_style="tool_call_param")
    parser = TaggedCallParser(config)
    
    content = """开始处理数据。

<tool_call name="process_data">
<param name="input">raw_data.csv</param>
<param name="format">json</param>
</tool_call>

处理完成，现在进行验证。

<tool_call name="validate_result">
<param name="data">processed_data</param>
<param name="schema">validation_schema.json</param>
</tool_call>

验证通过。"""
    
    print("📝 原始内容:")
    print(content)
    print("\n" + "=" * 50)
    
    result = parser.parse_message(content)
    
    print("🔍 解析结果 (按顺序):")
    for i, item in enumerate(result):
        if isinstance(item, str):
            print(f"{i+1}. 📄 文本: {repr(item)}")
        elif isinstance(item, TaggedToolCall):
            print(f"{i+1}. 🔧 工具调用: {item.tool_name}")
            print(f"   参数: {item.args}")
            print(f"   ID: {item.id}")


def demo_edge_cases():
    """演示边界情况"""
    print("\n\n🔧 边界情况演示")
    print("=" * 50)
    
    config = ToolCallConfig(format_style="call_direct")
    parser = TaggedCallParser(config)
    
    # 空内容
    print("1. 空内容:")
    result = parser.parse_message("")
    print(f"   结果: {result}")
    
    # 只有文本
    print("\n2. 只有文本:")
    result = parser.parse_message("这是一个普通的文本消息。")
    print(f"   结果: {result}")
    
    # 只有工具调用
    print("\n3. 只有工具调用:")
    result = parser.parse_message('<call tool="test"><param>value</param></call>')
    print(f"   结果: {result}")
    
    # 连续工具调用
    print("\n4. 连续工具调用:")
    result = parser.parse_message('<call tool="tool1"><p1>v1</p1></call><call tool="tool2"><p2>v2</p2></call>')
    print(f"   结果: {result}")


if __name__ == "__main__":
    demo_tool_calls_and_messages()
    demo_tool_call_param_format()
    demo_edge_cases()
    
    print("\n\n✅ 演示完成！")
    print("tool_calls_and_messages 功能已成功实现，能够按顺序记录工具调用和消息。")
