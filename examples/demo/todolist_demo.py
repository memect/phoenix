#!/usr/bin/env python3
"""
TodoList Agent Demo - 智能待办事项管理助手

这个演示展示了如何使用 nopagent/react_agent 框架创建一个可以根据用户自然语言要求
更新待办事项列表的智能助手。

运行方式:
    uv run python examples/demo/todolist_demo.py
"""

import asyncio
import logging
from typing import List
from pydantic import Field, ConfigDict

from nopagent.react_agent import ReactAgent, ReactAgentState, tool, get_current_state
from extract_agent.core.settings.llm_config import Settings

settings = Settings()
from extract_agent.core.recorder.jsonline_recorder import JsonLineRecorder
from extract_agent.core.llm.llm import get_llm_by_name


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TodoItem:
    """待办事项类"""
    def __init__(self, id: int, title: str, completed: bool = False, priority: str = "中"):
        self.id = id
        self.title = title
        self.completed = completed
        self.priority = priority  # 高、中、低
    
    def __repr__(self):
        status = "✅" if self.completed else "📋"
        priority_emoji = {"高": "🔥", "中": "⚡", "低": "💤"}.get(self.priority, "⚡")
        return f"{status} [{self.id}] {priority_emoji} {self.title}"

    def __str__(self) -> str:
        return self.__repr__()

class TodoListState(ReactAgentState):
    """TodoList Agent 的状态"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    todos: List[TodoItem] = Field(default_factory=list)
    next_id: int = 1
    
    def add_todo(self, title: str, priority: str = "中") -> TodoItem:
        """添加待办事项"""
        todo = TodoItem(self.next_id, title, priority=priority)
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
    
    def update_priority(self, todo_id: int, priority: str) -> bool:
        """更新优先级"""
        for todo in self.todos:
            if todo.id == todo_id:
                todo.priority = priority
                return True
        return False

    def print_todos(self):
        """打印待办事项"""
        for todo in self.todos:
            print(todo)


# ==================== 工具定义 ====================

@tool("add_todo")
def add_todo(title: str, priority: str = "中") -> str:
    """
    添加一个新的待办事项
    
    Args:
        title: 待办事项标题
        priority: 优先级，可选值：高、中、低，默认为中
    """
    state = get_current_state()
    if priority not in ["高", "中", "低"]:
        priority = "中"
    
    todo = state.add_todo(title, priority)
    return f"✅ 成功添加待办事项: {todo}"


@tool("complete_todo") 
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


@tool("delete_todo")
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


@tool("update_priority")
def update_priority(todo_id: int, priority: str) -> str:
    """
    更新待办事项的优先级
    
    Args:
        todo_id: 待办事项ID
        priority: 新的优先级，可选值：高、中、低
    """
    state = get_current_state()
    if priority not in ["高", "中", "低"]:
        return f"❌ 优先级必须是：高、中、低"
    
    success = state.update_priority(todo_id, priority)
    if success:
        return f"🔄 成功更新待办事项 ID {todo_id} 的优先级为: {priority}"
    else:
        return f"❌ 未找到ID为 {todo_id} 的待办事项"


@tool("list_todos")
def list_todos() -> str:
    """查看所有待办事项"""
    state = get_current_state()
    if not state.todos:
        return "📝 您的待办事项列表是空的"
    
    result = "📋 您的待办事项：\n"
    
    # 按优先级分组显示
    high_todos = [t for t in state.todos if t.priority == "高"]
    mid_todos = [t for t in state.todos if t.priority == "中"]
    low_todos = [t for t in state.todos if t.priority == "低"]
    
    for priority, todos in [("🔥 高优先级", high_todos), 
                           ("⚡ 中优先级", mid_todos), 
                           ("💤 低优先级", low_todos)]:
        if todos:
            result += f"\n{priority}:\n"
            for todo in todos:
                result += f"  {todo}\n"
    
    active_count = sum(1 for todo in state.todos if not todo.completed)
    completed_count = len(state.todos) - active_count
    result += f"\n📊 统计: {active_count} 个未完成, {completed_count} 个已完成"
    
    return result


@tool("get_stats")
def get_stats() -> str:
    """获取待办事项统计信息"""
    state = get_current_state()
    total = len(state.todos)
    completed = sum(1 for todo in state.todos if todo.completed)
    active = total - completed
    
    # 按优先级统计
    high_count = sum(1 for todo in state.todos if todo.priority == "高" and not todo.completed)
    mid_count = sum(1 for todo in state.todos if todo.priority == "中" and not todo.completed)
    low_count = sum(1 for todo in state.todos if todo.priority == "低" and not todo.completed)
    
    return f"""📊 统计信息:
总共 {total} 个待办事项
• 已完成: {completed} 个 ✅
• 未完成: {active} 个 📋
  - 🔥 高优先级: {high_count} 个
  - ⚡ 中优先级: {mid_count} 个  
  - 💤 低优先级: {low_count} 个"""


@tool(response_format='content_and_artifact')
def finish_task() -> tuple[None, dict]:
    """结束此次任务"""
    state = get_current_state()
    return None, {
        "type": "state_update",
        "state": {
            "should_stop": True,
            "stop_reason": "任务已完成"
        }
    }


# ==================== TodoList Agent ====================

class TodoListAgent(ReactAgent[TodoListState]):
    """智能 TodoList 管理助手"""
    
    def __init__(self, **kwargs):
        todo_tools = [add_todo, complete_todo, delete_todo, update_priority,
            list_todos, get_stats, finish_task]
        
        super().__init__(
            tools=todo_tools,
            state_class=TodoListState,
            max_iterations=10,
            **kwargs
        )
    
    def create_system_prompt(self, tools, state: TodoListState) -> str:
        """创建专门的系统提示"""
        active_count = sum(1 for todo in state.todos if not todo.completed)
        completed_count = len(state.todos) - active_count
        
        return f"""你是一个智能的 TodoList 管理助手。你可以帮助用户管理待办事项。

📝 **功能**:
• 添加新的待办事项（支持设置优先级：高、中、低）
• 标记待办事项为已完成  
• 删除待办事项
• 更新待办事项优先级
• 查看所有待办事项（按优先级分组显示）
• 获取统计信息
• 结束此次任务


💡 **使用建议**:
- 不要问用户任何内容
- 不要询问用户下一步做什么，直接采取行动。
- 当你觉得任务完成后，调用 finish_task 工具结束此次任务, 不要等待用户输入。
- 当你没有事可做了，调用 finish_task 工具结束此次任务, 不要等待用户输入。
- 请务必先思考，然后采取行动。
- 请使用工具来管理待办事项。
- 理解用户的自然语言需求
- 根据用户描述判断任务优先级
- 提供清晰的操作反馈
- 主动展示相关统计信息

请根据用户的要求，选择合适的工具来帮助管理他们的待办事项。"""


# ==================== 演示函数 ====================

async def interactive_demo():
    """交互式演示"""
    print("🚀 TodoList 智能助手启动！")
    print("=" * 50)
    print("💡 提示：输入 'quit' 或 'exit' 退出")
    print("=" * 50)
    
    # 这里应该使用真实的 LLM，演示中使用模拟
    recorder = JsonLineRecorder('local/logs/mocks/todolist_agent.jsonl')
    code_llm=get_llm_by_name(settings.llm_config, settings.code_llm, recorder)
    
    # 创建 Agent
    todo_list_agent = TodoListAgent(llm=code_llm._model, 
        system_prompt = f"""你是一个智能的 TodoList 管理助手。你可以帮助用户管理待办事项。
        📝 **功能**:
        • 添加新的待办事项（支持设置优先级：高、中、低）
        • 标记待办事项为已完成  
        • 删除待办事项
        • 更新待办事项优先级
        • 查看所有待办事项（按优先级分组显示）
        • 获取统计信息
        • 结束此次任务


        💡 **使用建议**:
        - 不要问用户任何内容
        - 不要询问用户下一步做什么，直接采取行动。
        - 当你觉得任务完成后，调用 finish_task 工具结束此次任务, 不要等待用户输入。
        - 当你没有事可做了，调用 finish_task 工具结束此次任务, 不要等待用户输入。
        - 请务必先思考，然后采取行动。
        - 请使用工具来管理待办事项。
        - 理解用户的自然语言需求
        - 根据用户描述判断任务优先级
        - 提供清晰的操作反馈
        - 主动展示相关统计信息

        请根据用户的要求，选择合适的工具来帮助管理他们的待办事项。"""
    )
    initial_state = TodoListState()
    
    # 添加一些示例数据
    initial_state.add_todo("完成项目文档", "高")
    initial_state.add_todo("买菜做饭", "中")
    initial_state.add_todo("健身锻炼", "低")
    
    result = await todo_list_agent.run(initial_state=initial_state, user_input="请添加一个待办事项：学习 Python，并分解任务")

    result.final_state.print_todos()
    
    


def batch_demo():
    """批量操作演示"""
    print("🔥 批量操作演示")
    print("=" * 30)
    
    from unittest.mock import Mock
    from nopagent.react_agent.tools import StateContext
    
    mock_llm = Mock()
    mock_llm.bind_tools = Mock(return_value=mock_llm)
    
    # 创建 Agent  
    TodoListAgent(llm=mock_llm)
    state = TodoListState()
    
    # 批量添加任务
    tasks = [
        ("学习 Python 新特性", "高"),
        ("整理书桌", "低"),
        ("准备年度总结", "高"),
        ("看电影放松", "低"),
        ("制定下周计划", "中"),
    ]
    
    with StateContext(state):
        print("📝 批量添加任务...")
        for title, priority in tasks:
            result = add_todo.invoke({"title": title, "priority": priority})
            print(f"  {result}")
        
        print(f"\n📋 当前所有任务:")
        print(list_todos.invoke({}))
        
        print(f"\n📊 统计信息:")
        print(get_stats.invoke({}))


if __name__ == "__main__":
    print("🎯 TodoList Agent 演示程序")
    print("=" * 50)
    
    # 运行交互式演示
    asyncio.run(interactive_demo())
    