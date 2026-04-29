#!/usr/bin/env python3
"""
TodoList Agent Demo with Tagged Tools - 智能待办事项管理助手（支持 Tagged Calling）

这个演示展示了如何使用 nopagent/react_agent 框架的新 tagged calling 功能
创建一个可以根据用户自然语言要求更新待办事项列表的智能助手。

Tagged calling 的优势:
- 无需转义复杂字符串参数（如JSON、多行文本）
- XML 标签格式更清晰易读
- 支持长文本和多行参数
- 自动类型转换

运行方式:
    uv run python examples/demo/todolist_tagged_demo.py
"""

import asyncio
import json
import logging
import tempfile
import os
from typing import List
from pydantic import Field, ConfigDict
from langchain_core.tools import tool

from nopagent.react_agent import ReactAgent, ReactAgentState, get_current_state
from nopagent.react_agent.tool_wrappers import agent_tool
from nopagent.react_agent.models import ToolCallConfig
from extract_agent.core.settings.llm_config import Settings

settings = Settings()
from extract_agent.core.recorder.jsonline_recorder import JsonLineRecorder
from extract_agent.core.llm.llm import get_llm_by_name
from nopagent.react_agent.prompts import get_tool_rule_prompt
# 添加新的 ReactAgentRecorder 相关导入
from nopagent.tracking import EventRecorder, DatabaseHandler
from nopagent.react_agent.recorder import ReactAgentRecorder


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TodoItem:
    """待办事项类"""
    def __init__(self, id: int, title: str, completed: bool = False, priority: str = "中", 
                 description: str = "", category: str = "通用", tags: List[str] = None):
        self.id = id
        self.title = title
        self.completed = completed
        self.priority = priority  # 高、中、低
        self.description = description
        self.category = category
        self.tags = tags or []
    
    def __repr__(self):
        status = "✅" if self.completed else "📋"
        priority_emoji = {"高": "🔥", "中": "⚡", "低": "💤"}.get(self.priority, "⚡")
        tags_str = f" #{','.join(self.tags)}" if self.tags else ""
        return f"{status} [{self.id}] {priority_emoji} [{self.category}] {self.title}{tags_str}"

    def __str__(self) -> str:
        return self.__repr__()
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            "id": self.id,
            "title": self.title,
            "completed": self.completed,
            "priority": self.priority,
            "description": self.description,
            "category": self.category,
            "tags": self.tags
        }


class TodoListState(ReactAgentState):
    """TodoList Agent 的状态"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    todos: List[TodoItem] = Field(default_factory=list)
    next_id: int = 1
    categories: List[str] = Field(default_factory=lambda: ["通用", "工作", "学习", "生活", "健康"])
    
    def add_todo(self, title: str, priority: str = "中", description: str = "", 
                 category: str = "通用", tags: List[str] = None) -> TodoItem:
        """添加待办事项"""
        todo = TodoItem(self.next_id, title, priority=priority, 
                       description=description, category=category, tags=tags)
        self.todos.append(todo)
        self.next_id += 1
        return todo
    
    def complete_todo(self, todo_id: int) -> bool:
        """完成待办事项"""
        for todo in self.todos:
            if todo.id == todo_id and not todo.completed:
                todo.completed = True
                return True
        return False
    
    def delete_todo(self, todo_id: int) -> bool:
        """删除待办事项"""
        for i, todo in enumerate(self.todos):
            if todo.id == todo_id:
                self.todos.pop(i)
                return True
        return False
    
    def update_todo(self, todo_id: int, **updates) -> bool:
        """更新待办事项"""
        for todo in self.todos:
            if todo.id == todo_id:
                for key, value in updates.items():
                    if hasattr(todo, key):
                        setattr(todo, key, value)
                return True
        return False

    def search_todos(self, query: str = "", category: str = "", tag: str = "", 
                    priority: str = "", completed: bool = None) -> List[TodoItem]:
        """搜索待办事项"""
        results = self.todos
        
        if query:
            results = [t for t in results if query.lower() in t.title.lower() or 
                      query.lower() in t.description.lower()]
        
        if category:
            results = [t for t in results if t.category == category]
            
        if tag:
            results = [t for t in results if tag in t.tags]
            
        if priority:
            results = [t for t in results if t.priority == priority]
            
        if completed is not None:
            results = [t for t in results if t.completed == completed]
            
        return results

    def print_todos(self):
        """打印待办事项"""
        for todo in self.todos:
            print(todo)


# ==================== Tagged Tool 定义 ====================

@agent_tool(types=['tagged'])
def add_todo(title: str, priority: str = "中", description: str = "", 
             category: str = "通用", tags: str = "") -> str:
    """
    添加一个新的待办事项（支持复杂参数和多行文本）
    
    Args:
        title: 待办事项标题
        priority: 优先级，可选值：高、中、低，默认为中
        description: 详细描述（支持多行文本）
        category: 分类，默认为通用
        tags: 标签，用逗号分隔（如: 重要,紧急,个人）
    """
    state = get_current_state()
    
    if priority not in ["高", "中", "低"]:
        priority = "中"
    
    if category not in state.categories:
        state.categories.append(category)
    
    # 处理标签
    tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []
    
    todo = state.add_todo(title, priority, description, category, tag_list)
    return f"✅ 成功添加待办事项: {todo}\n描述: {description}" if description else f"✅ 成功添加待办事项: {todo}"


@agent_tool(types=['tagged'])
def add_todos_batch(todos_json: str) -> str:
    """
    批量添加待办事项（使用JSON格式，展示tagged calling处理复杂数据的优势）
    
    Args:
        todos_json: JSON格式的待办事项列表，包含title, priority, description等字段
    """
    state = get_current_state()
    
    try:
        todos_data = json.loads(todos_json)
        if not isinstance(todos_data, list):
            return "❌ 请提供待办事项数组格式的JSON"
        
        added_todos = []
        for todo_data in todos_data:
            if not isinstance(todo_data, dict) or 'title' not in todo_data:
                continue
                
            title = todo_data.get('title', '')
            priority = todo_data.get('priority', '中')
            description = todo_data.get('description', '')
            category = todo_data.get('category', '通用')
            tags = todo_data.get('tags', [])
            
            if priority not in ["高", "中", "低"]:
                priority = "中"
                
            todo = state.add_todo(title, priority, description, category, tags)
            added_todos.append(todo)
        
        return f"🎉 成功批量添加 {len(added_todos)} 个待办事项:\n" + "\n".join(str(todo) for todo in added_todos)
        
    except json.JSONDecodeError:
        return "❌ JSON格式错误，请提供有效的JSON数据"


@agent_tool(types=['tagged'])
def complete_todo(todo_id: int) -> str:
    """
    标记指定ID的待办事项为已完成
    
    Args:
        todo_id: 待办事项ID
    """
    state = get_current_state()
    success = state.complete_todo(todo_id)
    if success:
        return f"🎉 成功完成待办事项 ID: {todo_id}"
    else:
        return f"❌ 未找到ID为 {todo_id} 的待办事项或已完成"


@agent_tool(types=['tagged'])
def delete_todo(todo_id: int) -> str:
    """
    删除指定ID的待办事项
    
    Args:
        todo_id: 待办事项ID
    """
    state = get_current_state()
    success = state.delete_todo(todo_id)
    if success:
        return f"🗑️ 成功删除待办事项 ID: {todo_id}"
    else:
        return f"❌ 未找到ID为 {todo_id} 的待办事项"


@agent_tool(types=['tagged'])
def update_todo(todo_id: int, title: str = "", priority: str = "", 
                description: str = "", category: str = "", tags: str = "") -> str:
    """
    更新待办事项的信息（支持多字段更新）
    
    Args:
        todo_id: 待办事项ID
        title: 新标题（可选）
        priority: 新优先级（可选）：高、中、低
        description: 新描述（可选，支持多行文本）
        category: 新分类（可选）
        tags: 新标签（可选），用逗号分隔
    """
    state = get_current_state()
    
    # 构建更新数据
    updates = {}
    if title:
        updates['title'] = title
    if priority and priority in ["高", "中", "低"]:
        updates['priority'] = priority
    if description:
        updates['description'] = description
    if category:
        updates['category'] = category
        if category not in state.categories:
            state.categories.append(category)
    if tags:
        updates['tags'] = [tag.strip() for tag in tags.split(",") if tag.strip()]
    
    if not updates:
        return "❌ 请提供至少一个要更新的字段"
    
    success = state.update_todo(todo_id, **updates)
    if success:
        updated_fields = ", ".join(updates.keys())
        return f"🔄 成功更新待办事项 ID {todo_id} 的字段: {updated_fields}"
    else:
        return f"❌ 未找到ID为 {todo_id} 的待办事项"


@agent_tool(types=['tagged'])
def search_todos(query: str = "", category: str = "", tag: str = "", 
                priority: str = "", completed: str = "all") -> str:
    """
    搜索和筛选待办事项
    
    Args:
        query: 搜索关键词（在标题和描述中搜索）
        category: 筛选分类
        tag: 筛选标签
        priority: 筛选优先级：高、中、低
        completed: 筛选完成状态：all（全部）、true（已完成）、false（未完成）
    """
    state = get_current_state()
    
    # 处理完成状态参数
    completed_filter = None
    if completed == "true":
        completed_filter = True
    elif completed == "false":
        completed_filter = False
    
    results = state.search_todos(query, category, tag, priority, completed_filter)
    
    if not results:
        return "🔍 没有找到符合条件的待办事项"
    
    result_text = f"🔍 找到 {len(results)} 个符合条件的待办事项:\n\n"
    
    # 按优先级分组显示
    high_todos = [t for t in results if t.priority == "高"]
    mid_todos = [t for t in results if t.priority == "中"]
    low_todos = [t for t in results if t.priority == "低"]
    
    for priority, todos in [("🔥 高优先级", high_todos), 
                           ("⚡ 中优先级", mid_todos), 
                           ("💤 低优先级", low_todos)]:
        if todos:
            result_text += f"{priority}:\n"
            for todo in todos:
                desc_preview = f" - {todo.description[:50]}..." if todo.description else ""
                result_text += f"  {todo}{desc_preview}\n"
    
    return result_text


@agent_tool(types=['tagged'])
def list_todos() -> str:
    """查看所有待办事项（按分类和优先级组织显示）"""
    state = get_current_state()
    if not state.todos:
        return "📝 您的待办事项列表是空的"
    
    result = "📋 您的待办事项：\n"
    
    # 按分类分组显示
    for category in state.categories:
        category_todos = [t for t in state.todos if t.category == category]
        if category_todos:
            result += f"\n📁 {category}:\n"
            
            # 在每个分类内按优先级排序
            high_todos = [t for t in category_todos if t.priority == "高"]
            mid_todos = [t for t in category_todos if t.priority == "中"]  
            low_todos = [t for t in category_todos if t.priority == "低"]
            
            for todos in [high_todos, mid_todos, low_todos]:
                for todo in todos:
                    desc_preview = f" - {todo.description[:30]}..." if todo.description else ""
                    result += f"  {todo}{desc_preview}\n"
    
    # 统计信息
    active_count = sum(1 for todo in state.todos if not todo.completed)
    completed_count = len(state.todos) - active_count
    result += f"\n📊 统计: {active_count} 个未完成, {completed_count} 个已完成"
    
    return result


@agent_tool(types=['tagged'])
def get_detailed_stats() -> str:
    """获取详细的待办事项统计信息"""
    state = get_current_state()
    total = len(state.todos)
    if total == 0:
        return "📊 统计信息: 暂无待办事项"
    
    completed = sum(1 for todo in state.todos if todo.completed)
    active = total - completed
    
    # 按优先级统计
    high_count = sum(1 for todo in state.todos if todo.priority == "高" and not todo.completed)
    mid_count = sum(1 for todo in state.todos if todo.priority == "中" and not todo.completed)
    low_count = sum(1 for todo in state.todos if todo.priority == "低" and not todo.completed)
    
    # 按分类统计
    category_stats = {}
    for todo in state.todos:
        if not todo.completed:
            category_stats[todo.category] = category_stats.get(todo.category, 0) + 1
    
    # 收集所有标签
    all_tags = set()
    for todo in state.todos:
        all_tags.update(todo.tags)
    
    result = f"""📊 详细统计信息:
    
📈 总体情况:
• 总共: {total} 个待办事项
• 已完成: {completed} 个 ✅ ({completed/total*100:.1f}%)
• 未完成: {active} 个 📋 ({active/total*100:.1f}%)

🔥 优先级分布（未完成）:
• 高优先级: {high_count} 个
• 中优先级: {mid_count} 个  
• 低优先级: {low_count} 个

📁 分类分布（未完成）:"""

    for category, count in sorted(category_stats.items()):
        result += f"\n• {category}: {count} 个"
    
    if all_tags:
        result += f"\n\n🏷️ 使用的标签: {', '.join(sorted(all_tags))}"
    
    return result


@agent_tool(types=['tagged'])
def export_todos_json() -> str:
    """导出所有待办事项为JSON格式（展示tagged calling处理复杂输出的能力）"""
    state = get_current_state()
    
    todos_data = {
        "export_info": {
            "timestamp": "2024-01-01T00:00:00Z",
            "total_count": len(state.todos),
            "categories": state.categories
        },
        "todos": [todo.to_dict() for todo in state.todos]
    }
    
    json_output = json.dumps(todos_data, ensure_ascii=False, indent=2)
    
    return f"""📤 导出完成！待办事项JSON数据：

```json
{json_output}
```

💡 这个JSON可以用于备份、分享或导入其他系统。使用tagged calling的优势是可以完美处理这种复杂的多行输出，无需转义！"""


@agent_tool(types=['tagged'])
@tool(response_format='content_and_artifact')
def finish_task() -> tuple[str, dict]:
    """结束此次任务（只支持tagged calling，展示工具类型限制）"""
    state = get_current_state()
    return "✨ 任务已完成！感谢使用TodoList智能助手。", {
        "type": "state_update",
        "state": {
            "should_stop": True,
            "stop_reason": "任务已完成"
        }
    }


# ==================== TodoList Tagged Agent ====================

class TodoListTaggedAgent(ReactAgent[TodoListState]):
    """支持 Tagged Calling 的智能 TodoList 管理助手"""
    
    def __init__(self, **kwargs):
        # 配置 Tagged Calling
        tool_call_config = ToolCallConfig(
            format_style="call_direct",  # 使用 <call tool="name"> 格式
            enable_function_calling=True,   # 同时支持function calling
            enable_tagged_calling=True,     # 启用tagged calling
            processing_mode="priority",     # tagged calling优先
            error_strategy="log_and_continue"
        )
        
        tagged_tools = [
            add_todo, add_todos_batch, complete_todo, delete_todo, update_todo,
            search_todos, list_todos, get_detailed_stats, export_todos_json, finish_task
        ]
        
        super().__init__(
            tools=tagged_tools,
            state_class=TodoListState,
            max_iterations=15,
            tool_call_config=tool_call_config,
            **kwargs
        )
    
    def create_system_prompt(self, tools, state: TodoListState) -> str:
        """创建支持Tagged Calling的系统提示"""
        active_count = sum(1 for todo in state.todos if not todo.completed)
        completed_count = len(state.todos) - active_count
        tool_rule_prompt = get_tool_rule_prompt(tools, self.tool_call_config)

        
        return f"""{tool_rule_prompt}

你是一个智能的 TodoList 管理助手，支持强大的 Tagged Calling 功能。

📝 **核心功能**:
• 添加待办事项（支持优先级、分类、标签、详细描述）
• 批量添加待办事项（使用JSON格式）
• 完成/删除/更新待办事项
• 智能搜索和筛选
• 分类和标签管理
• 详细统计分析
• JSON格式导出
• 任务结束


💡 **使用指南**:
- 理解用户自然语言需求，智能判断优先级和分类
- 提供清晰的操作反馈
- 主动展示相关信息
- 完成任务后调用finish_task结束

请根据用户要求，选择合适的工具来管理他们的待办事项。优先展示tagged calling的强大功能！"""


# ==================== 演示函数 ====================

async def interactive_demo():
    """交互式演示"""
    print("🚀 TodoList Tagged Calling 智能助手启动！")
    print("=" * 60)
    print("💡 本演示展示了tagged calling的强大功能：")
    print("   • 处理复杂JSON参数")
    print("   • 多行文本描述")
    print("   • 无需字符串转义")
    print("   • XML标签格式清晰")
    print("   • ReactAgent 事件追踪和记录")
    print("=" * 60)
    
    # 创建临时数据库用于事件追踪
    db_path = 'local/recorder/todolist_tagged_agent.db'
    
    try:
        # 使用真实的 LLM
        recorder = JsonLineRecorder('local/logs/mocks/todolist_tagged_agent.jsonl')
        code_llm = get_llm_by_name(settings.llm_config, settings.code_llm, recorder)
        
        # 创建事件记录器
        db_handler = DatabaseHandler(db_path)
        event_recorder = EventRecorder()
        event_recorder.add_handler(db_handler)
        
        # 创建 ReactAgent 记录器
        agent_recorder = ReactAgentRecorder(
            agent_id="todolist_tagged_agent",
            agent_name="TodoList Tagged Calling 智能助手",
            event_recorder=event_recorder
        )
        
        print(f"📊 事件数据库创建于: {db_path}")
        
        # 创建支持 Tagged Calling 的 Agent（带记录器）
        tagged_agent = TodoListTaggedAgent(llm=code_llm._model, recorder=agent_recorder)
        
        # 创建初始状态
        initial_state = TodoListState()
        
        # 添加一些示例数据展示标签和分类功能
        initial_state.add_todo("完成项目文档", "高", "需要编写API文档和用户手册", "工作", ["重要", "文档"])
        initial_state.add_todo("学习新技术", "中", "研究React和Vue的最新特性", "学习", ["技术", "前端"])
        initial_state.add_todo("健身计划", "低", "每周3次健身房锻炼", "健康", ["运动", "计划"])
        
        # 演示复杂的用户请求
        # complex_request = """需要 学习如何使用python开发一个web应用的todo"""
        complex_request = """加一个todo： 睡觉, 然后结束任务"""
        
        print(f"📝 用户请求: {complex_request}")
        print("\n🔄 Agent 处理中...")
        print("=" * 60)
        
        # 运行 Agent
        result = await tagged_agent.run(
            initial_state=initial_state, 
            user_input=complex_request
        )
        
        print("\n" + "=" * 60)
        print("✨ 任务执行完成！")
        print("📊 最终状态:")
        result.final_state.print_todos()
        
        # 展示事件记录
        print("\n" + "=" * 60)
        print("📋 事件记录统计:")
        events = db_handler.query_events(entity_filters={"entity_id": "todolist_tagged_agent"})
        
        lifecycle_events = [e for e in events if e.tag == "lifecycle"]
        message_events = [e for e in events if e.tag == "message"]
        
        print(f"🔄 生命周期事件: {len(lifecycle_events)}")
        print(f"💬 消息事件: {len(message_events)}")
        print(f"📊 总计: {len(events)} 个事件")
        
        print("\n📝 最近的事件:")
        for i, event in enumerate(events[-5:], 1):  # 显示最后5个事件
            print(f"   {i}. [{event.sub_tag}] {event.display}")
        
        print(f"\n💾 完整事件数据保存在: {db_path}")
        print("   可以使用数据库工具查看详细信息")
        
    except Exception as e:
        print(f"❌ 演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 询问是否保留数据库文件
        print(f"\n🗂️ 事件数据库位于: {db_path}")
        keep_db = input("是否保留事件数据库文件以便后续查看? (y/N): ").lower().startswith('y')
        
        if not keep_db and os.path.exists(db_path):
            os.unlink(db_path)
            print("🗑️ 临时数据库已清理")




if __name__ == "__main__":
    print("🎯 TodoList Tagged Calling Agent 演示程序")
    print("展示新一代工具调用技术的强大能力")
    print("=" * 60)
    
    
    # 运行交互式演示
    asyncio.run(interactive_demo())