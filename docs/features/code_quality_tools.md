# AgentScope Agent 代码质量工具集成

## 背景

为了提升 AI Agent 的编码能力，集成了以下代码质量工具：
- **Ruff** - Python linter 和格式化工具
- **Tree-sitter CLI** - 代码结构分析工具
- **Mypy** - 静态类型检查（手动使用）
- **Pytest** - 测试框架（手动使用）

## 设计方案

### 核心思路

1. **工具保持纯粹** - 文件写入工具 (`write_text_file`, `insert_text_file`) 只负责写入，不做额外操作
2. **Hook 处理检查** - 通过 `post_acting` hook 在工具执行后自动运行 ruff check
3. **System 消息反馈** - 检查结果作为 system 消息注入 Agent 的 memory，Agent 在下一轮推理时能看到

### 为什么用 Hook 而不是在工具内检查？

最初考虑在 `write_text_file_enhanced` 工具内直接运行 ruff check 并修改返回值。但遇到问题：
- AgentScope Studio 对工具返回的 `ToolResponse` 格式有要求
- 修改返回内容可能导致 Studio 推送消息失败（400 Bad Request）

使用 Hook 的好处：
- 工具返回原生格式，不影响 Studio
- 检查结果作为独立的 system 消息，清晰分离
- 解耦：文件写入和代码检查是两个独立的反馈

## 实现细节

### 文件结构

```
src/agentscope_agent/
├── tools/
│   └── file_tools.py          # 文件写入工具（简化版，只有行数限制）
├── hooks/
│   ├── __init__.py
│   └── ruff_check.py          # Ruff check hook
└── agents/
    └── extract_dev.py         # 注册 hook
```

### Ruff Check Hook

位置：`src/agentscope_agent/hooks/ruff_check.py`

```python
async def ruff_check_hook(self, kwargs: dict, output: Any) -> Any:
    """post_acting hook: 检测文件写入工具，对 .py 文件运行 ruff check"""
    tool_call = kwargs.get("tool_call")
    if not tool_call:
        return output
    
    tool_name = tool_call.get("name", "")
    tool_input = tool_call.get("input", {})
    
    # 检查是否是文件写入工具
    if tool_name not in ("write_text_file", "insert_text_file", ...):
        return output
    
    file_path = tool_input.get("file_path", "")
    if not file_path.endswith(".py"):
        return output
    
    # 同步运行 ruff check
    issues = run_ruff_check_sync(file_path)
    
    if issues:
        issues_text = format_ruff_issues(issues, file_path)
        system_msg = Msg(name="system", content=issues_text, role="system")
        await self.memory.add(system_msg)
    
    return output
```

### Hook 注册

在 `create_extract_dev_agent()` 中注册：

```python
from ..hooks import register_ruff_check_hook

agent = ReActAgent(...)
register_ruff_check_hook(agent)
```

### 执行时序

1. Agent 调用 `write_text_file` 工具
2. 工具执行，文件写入成功
3. 工具结果添加到 memory（在 `_acting` 的 finally 块）
4. `post_acting` hook 执行
5. Hook 检测到是 `.py` 文件，运行 `ruff check`
6. 如果有问题，创建 system 消息添加到 memory
7. Agent 下一轮推理时看到工具结果和检查结果

### 输出格式

```
[自动代码检查] 发现 2 个问题：
  - line 4: F401 `module.unused` imported but unused [可自动修复]
  - line 10: E501 Line too long (120 > 88)
提示：运行 `ruff check --fix /path/to/file.py` 可自动修复 1 个问题
```

## Tree-sitter CLI

独立的命令行工具，Agent 通过 `execute_shell_command` 使用。

位置：`src/tree_sitter_cli.py`

### 命令

```bash
# 分析文件结构（返回代码骨架）
tree-sitter-cli analyze <file.py>

# 查找符号定义
tree-sitter-cli find-symbol <file.py> <symbol_name>

# 列出所有符号
tree-sitter-cli list-symbols <file.py>
```

### analyze 输出示例

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class AgentScopeAgentSettings (BaseSettings) :
    model_config = ...
    model: str | None = None
    timeout: float = 300.0
    def with_overrides (...) -> "AgentScopeAgentSettings" : ...

_settings: AgentScopeAgentSettings | None = None

def get_settings () -> AgentScopeAgentSettings : ...
```

特点：
- 省略函数体（用 `...` 表示）
- 省略长字符串字面量（超过 60 字符或多行）
- 保留类型注解
- 合理的空行分隔

## 依赖

在 `pyproject.toml` 中添加：

```toml
# --- code quality tools for agent ---
"tree-sitter>=0.24.0",
"tree-sitter-python>=0.23.0",
"ruff>=0.8.0",
"mypy>=1.0.0",
"pytest-cov>=4.0.0",
```

## Agent Prompt

工具使用指南集成在 Agent 的 system prompt 中：

- `src/agentscope_agent/prompts/tools/ruff.py` - Ruff 使用指南
- `src/agentscope_agent/prompts/tools/tree_sitter.py` - Tree-sitter CLI 使用指南
- `src/agentscope_agent/prompts/tools/mypy.py` - Mypy 使用指南
- `src/agentscope_agent/prompts/tools/pytest_cov.py` - Pytest 使用指南

## 相关文档

- `docs/agent_code_tools_setup.md` - 安装说明
- `docs/tool_tree_sitter_cli.md` - Tree-sitter CLI 详细使用指南
