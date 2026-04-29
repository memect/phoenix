# AgentScope Agent 设计文档

基于 AgentScope 框架实现的提取程序优化 Agent，负责在 workspace 中自动编写/优化 `program.py`，并通过 `extract-dev` 命令持续评估与迭代。

## 目标与范围

- **目标**：自主完成提取程序优化，提升准确率与召回率（提示词要求 >99%）。
- **范围**：仅覆盖 `agentscope_agent` 模块的设计、运行流程、工作目录、工具与提示词规范。

## 模块结构

```
src/agentscope_agent/
├── __init__.py            # 包入口
├── __main__.py            # CLI 启动
├── cli.py                 # CLI 入口
├── config.py              # 配置管理
├── model_factory.py       # 模型工厂（支持多提供商）
├── workflow.py            # 主流程编排
│
├── prompts/               # 提示词模块
│   ├── __init__.py
│   ├── extract_dev.py     # ExtractDevAgent 提示词
│   ├── supervisor.py      # Supervisor 提示词
│   ├── business.py        # BusinessAgent 提示词
│   ├── labeling.py        # LabelingAgent 提示词
│   ├── code_agent.py      # CodeAgent 提示词
│   └── strategies.py      # 强制策略提示词（指导工具使用）
│
├── tracking/              # 监控统计模块
│   ├── __init__.py
│   ├── token_stats.py     # Token 统计
│   └── model_wrapper.py   # 模型包装器（拦截并统计 token）
│
├── state/                 # 状态管理模块
│   ├── __init__.py
│   ├── saver.py          # 防抖状态保存器
│   └── manager.py        # Session 和状态管理
│
├── tools/                 # 工具模块
│   ├── __init__.py
│   ├── file_tools.py           # 带行数限制的文件工具
│   ├── business_agent_tool.py  # ask_business_agent 工具
│   └── labeling_workflow.py    # label_all_documents 并发标注工具
│
├── hooks/                 # Hook 模块
│   ├── __init__.py
│   ├── ruff_check.py           # ruff 代码检查 hook
│   └── timeout_reminder.py     # 超时提醒 hook
│
├── timeout.py             # 超时控制模块
│
└── agents/                # Agent 实现模块
    ├── __init__.py
    ├── extract_dev.py    # ExtractDevAgent 工厂函数
    ├── code_agent.py     # CodeAgent 工具创建
    ├── supervisor.py     # Supervisor 类（统一的监督者）
    ├── business.py       # BusinessAgent 类
    └── labeling.py       # LabelingAgent 类（并发标注）
```

### 模块职责

#### `tracking/` - 监控统计
- `TokenStats`: Token 使用统计数据类
- `TokenTrackingModelWrapper`: 拦截模型调用，自动统计 token 使用

#### `state/` - 状态管理
- `StateSaver`: 带防抖和单任务锁的状态保存器
- `SessionManager`: 统一管理 Session、Agent 状态、迭代计数、Token 统计
  - **tool_use 消息清理**：加载状态时自动检测并删除尾部未完成的 tool_use 消息（解决中断后恢复时 API 报错问题）

#### `prompts/` - 提示词管理
- `extract_dev.py`: ExtractDevAgent 的系统提示词（分 `_WITHOUT_CODE_AGENT` 和 `_WITH_CODE_AGENT` 两种模式）
- `supervisor.py`: SupervisorAgent 的系统提示词
- `business.py`: BusinessAgent 的系统提示词（含 `UNLABELED_SYSTEM_PROMPT`、Schema 类型说明）
- `labeling.py`: LabelingAgent 的系统提示词和 `build_label_message()` 消息构建函数
- `code_agent.py`: CodeAgent 的系统提示词

#### `agents/` - Agent 实现
- `create_extract_dev_agent()`: 创建配置好的 ExtractDevAgent
- `register_auto_save_hooks()`: 注册自动保存 hooks
- `create_code_agent_tool()`: 创建 CodeAgent 工具（可选）
- `Supervisor`: 统一的监督者类（支持可选的 BusinessAgent）
- `BusinessAgent`: 业务分析 Agent 类
- `LabelingAgent`: 并发标注 Agent 类（每次 `label_document()` 创建独立 ReActAgent 实例）

#### `tools/` - 工具模块
- `register_file_tools()`: 注册文件写入工具（支持可选行数限制）
- `create_limited_file_tools()`: 创建带行数限制的文件工具
- `ask_business_agent()`: 询问业务 Agent 的工具（启用 BusinessAgent 时可用）
- `set_business_agent()` / `get_business_agent()`: BusinessAgent 全局引用管理
- `create_label_all_documents_tool()`: 创建并发标注工具（无标注模式下注册到 BusinessAgent）

#### `hooks/` - Hook 模块
- `register_ruff_check_hook()`: 注册 ruff check hook（写入 .py 文件后自动检查）
- `register_timeout_reminder_hook()`: 注册超时提醒 hook

#### `timeout.py` - 超时控制模块
- `TimeoutReminder`: 超时提醒管理器
- `TimeoutReminderConfig`: 超时提醒配置
- `timeout_monitor()`: 超时监控协程（强制中断）
- `set_timeout_reminder()` / `get_timeout_reminder()`: 全局访问

#### `workflow.py` - 主流程
- `run_agent_async()`: 异步主流程，编排整个工作流
- `run_extract_dev_agent()`: 同步入口封装

## 运行入口

### CLI

`agentscope_agent/cli.py` 使用 Typer 定义命令行入口，参数优先级：**命令行 > 环境变量**。

#### 子命令

- `run` - 启动 Agent
- `test` - 测试模型 API 连通性

#### run 命令

```bash
python -m agentscope_agent run [OPTIONS]
```

可选参数：
- `--model/-m` → `ASA_MODEL`（格式：`provider/model_name`）
- `--api-base/-b` → `ASA_API_BASE`
- `--api-key/-k` → `ASA_API_KEY`
- `--workspace/-w` → workspace 路径
- `--supervisor-model` → Supervisor 模型（默认同 `--model`）
- `--max-iterations` → 最大迭代次数（默认 50）
- `--target-accuracy` → 目标准确率（默认 0.99）
- `--no-supervisor` → 禁用 Supervisor，使用单 Agent 模式
- `--reset` → 清除已有状态，重新开始
- `--api-timeout` → API 超时时间（秒，默认 300）
- `--run-timeout` → 运行总时长限制（秒），超时后优雅退出
- `--no-timeout-reminder` → 禁用超时提醒
- `--enable-code-agent` → 启用 CodeAgent 子代理（默认禁用）
- `--code-agent-model` → CodeAgent 模型（默认同 `--model`）
- `--limit-write-lines` → 启用文件写入行数限制模式
- `--max-write-lines` → 每次写入最大行数（默认 100）
- `--enable-business-agent` → 启用业务 Agent 模式
- `--business-agent-model` → 业务 Agent 模型（默认同 `--model`）
- `--labeling-model` → `ASA_LABELING_MODEL`（标注 Agent 模型）
- `--labeling-api-base` → `ASA_LABELING_API_BASE`（标注 Agent API 地址）
- `--labeling-api-key` → `ASA_LABELING_API_KEY`（标注 Agent API 密钥）
- `--studio-url` → AgentScope Studio URL（留空禁用）
- `--user-message` → `ASA_USER_MESSAGE`（自定义初始用户消息）
- `--user-message-file` → 从文件读取初始用户消息（优先级高于 `--user-message`）

#### test 命令

```bash
python -m agentscope_agent test [OPTIONS]
```

用于快速测试模型 API 连通性，发送简单测试请求并显示结果。

可选参数：
- `--model/-m` → `ASA_MODEL`
- `--api-base/-b` → `ASA_API_BASE`
- `--api-key/-k` → `ASA_API_KEY`
- `--timeout` → API 超时时间（秒，默认 30）

### 模块入口

`agentscope_agent/__main__.py` 直接调用 CLI app。

## 配置管理

`agentscope_agent/config.py` 使用 `pydantic-settings` 管理配置：

- `env_prefix = "ASA_"`
- `env_file = ".agentscope_agent.env"`
- 必填：`model / api_base / api_key`
- 支持 `with_overrides()` 用 CLI 参数覆盖环境变量。

## 模型配置

### 模型工厂

`model_factory.py` 根据模型前缀创建对应的模型和 formatter：

- `gemini/xxx` → `GeminiChatModel` + `GeminiChatFormatter`
- `openai/xxx` → `OpenAIChatModel` + `OpenAIChatFormatter`
- 无前缀默认使用 OpenAI

### Gemini 模型配置

对于 Gemini 模型（通过 API 中转站），`model_factory.py` 处理以下特殊配置：

1. **Base URL 处理**：移除 `/v1` 后缀（genai SDK 自动添加 `/v1beta`）
2. **Timeout 单位**：`HttpOptions.timeout` 单位是毫秒，需要将秒转换为毫秒
3. **代理配置**：
   - genai SDK 异步请求默认用 aiohttp，但 aiohttp 不支持构造函数传代理
   - 解决方案：传入配置好代理的 `httpxAsyncClient`，强制 SDK 用 httpx 做异步请求
   - 同步客户端通过 `clientArgs` 传递代理

### Thinking 模型限制

**注意**：Gemini thinking 模型（如 `gemini-3-flash-preview-thinking-*`）存在兼容性问题：

- Thinking 模型返回的 function call 需要包含 `thought_signature`
- AgentScope 目前不支持处理 `thought_signature`
- **建议使用非 thinking 模型**，如 `gemini-2.0-flash`

示例配置：

```bash
# 推荐：使用非 thinking 模型
uv run python -m agentscope_agent run --model gemini/gemini-2.0-flash --workspace ...

# 不推荐：thinking 模型可能报错
uv run python -m agentscope_agent run --model gemini/gemini-3-flash-preview-thinking-* --workspace ...
```

## 核心流程

核心执行逻辑位于 `agentscope_agent/workflow.py`：

1. **创建/复用 workspace**：`create_workspace()`
2. **初始化状态管理**：`SessionManager`（恢复历史状态）
3. **创建 Supervisor**（可选）：含可选的 BusinessAgent
4. **生成业务指导文档**（启用 BusinessAgent 时）：`business_guide.md`
5. **创建 ExtractDevAgent**：通过 `create_extract_dev_agent()` 工厂函数
6. **加载 Agent 状态**：从 Session 恢复 memory 和对话历史
   - 加载后自动清理尾部未完成的 tool_use 消息（防止中断后恢复时 API 报错）
7. **注册自动保存 hooks**：通过 `StateSaver` 防抖保存
8. **启动对话循环**：单 Agent / Supervisor / Supervisor+BusinessAgent 模式

### 工作目录初始化

`create_workspace()` 负责初始化 workspace：

- **目录创建**：`local/workspaces/<uuid>` 或传入路径
- **git init**：若 `.git` 不存在则初始化
- **写入 `.gitignore`**：忽略常见 dotfiles、缓存、虚拟环境
- **生成 `program.py` 模板**（若不存在）
- **生成 pytest 测试模板**：
  - `tests/conftest.py`
  - `tests/test_extract.py`

`setup_environment()` 会：

- 设置 `EXTRACT_PROGRAM` 指向 `program.py`
- `os.chdir(workspace)`，确保工具使用相对路径

### Workspace 结构

```
workspace/
├── program.py
├── tests/
│   ├── conftest.py
│   └── test_extract.py
├── docs/                    # 可选文档目录
└── .gitignore
```

### pytest 支持

`conftest.py` 配置 pytest 环境（将 workspace 加入 path）。

`test_extract.py` 提供硬编码测试示例模板。测试数据必须直接写在测试文件中，不依赖外部数据源。

### Git 规则

默认 `.gitignore` 会忽略：

- `.*` dotfiles（允许 `.gitignore/.gitkeep/.gitmodules`）
- Python 缓存、pytest 缓存、虚拟环境、`.cache/`
- `.DS_Store` 等系统文件

## PlanNotebook 同步

- Agent 初始化时创建 `PlanNotebook`。
- 计划用于当前回合决策，不再要求同步到固定的 workspace 文件路径。
- 如需沉淀计划，应由具体工作流显式决定写到哪个文档，而不是默认写入 `plan.md`。

## Agent 组成

### Agent

- `ReActAgent`：负责推理与工具调用
- `UserAgent`：负责终端交互
- `OpenAIChatModel`：LLM 模型配置
- `OpenAIChatFormatter`：对话格式化（Chat 角色）

### 工具

`Toolkit` 注册以下工具：

- `execute_shell_command`
- `view_text_file`
- `write_text_file` / `write_text_file_limited`（可选行数限制模式）
- `insert_text_file_limited`（仅在行数限制模式下注册）
- `PlanNotebook` 自带工具（`create_plan`、`update_subtask_state`、`finish_subtask`、`finish_plan` 等）
- `create_code_agent`（可选，需启用 `--enable-code-agent`）

## 提示词设计

`prompts/` 目录包含多组提示词：

### ExtractDevAgent Prompts

- `SYSTEM_PROMPT_BASE`：基本系统提示词（包含业务指导说明，启用 BusinessAgent 时可用）
- `SYSTEM_PROMPT_WITHOUT_CODE_AGENT`：未启用 CodeAgent 时的完整提示词
- `SYSTEM_PROMPT_WITH_CODE_AGENT`：启用 CodeAgent 时的完整提示词（包含 CodeAgent 工具使用说明）
- `build_initial_message()`：构建初始消息，支持自定义用户消息
- `get_initial_message()`：兼容旧接口（已废弃，请使用 `build_initial_message()`）

### 策略提示词（strategies.py）

`strategies.py` 定义 `STRATEGIES` 常量，用于指导 Agent 如何编写提取代码、使用哪些工具。

**策略的强制性**：
- 策略位于系统提示词的“初始化步骤”之后，标题为“强制策略（必须遵守）”
- 明确声明“优先级高于你的自主判断”
- 策略内容使用强制性语气（如“必须使用”、“禁止使用”）

**修改策略**：
- 编辑 `prompts/strategies.py` 中的 `STRATEGIES` 常量
- Agent 会按策略要求编写代码（如强制使用 VLMExtractTool）

### Supervisor Prompts

`prompts/supervisor.py` 提供两套提示词：

- `SYSTEM_PROMPT_WITHOUT_BUSINESS`：未启用 BusinessAgent 时的提示词
- `SYSTEM_PROMPT_WITH_BUSINESS`：启用 BusinessAgent 时的提示词（支持 `[BUSINESS]` 响应）
- `get_initial_message()`：生成 Supervisor 检查消息

### BusinessAgent Prompts

`prompts/business.py` 提供业务分析 Agent 的提示词：

- `SYSTEM_PROMPT`：业务分析职责、标准集理解、字段解释
- `UNLABELED_SYSTEM_PROMPT`：无标注模式提示词（含 Schema 类型说明、批量标注工具说明）
- `get_analyze_message()`：生成初始分析任务消息
- `get_unlabeled_analyze_message()`：生成无标注模式分析任务消息（含 `label_all_documents()` 工作流）
- `get_answer_question_message()`：回答业务问题的消息

### LabelingAgent Prompts

`prompts/labeling.py` 提供标注 Agent 的提示词：

- `SYSTEM_PROMPT`：标注专家角色、工作流程、标注格式说明（object / list_of_objects）
- `build_label_message(doc_id, dataset, schema_json, business_guide)`：构建标注任务消息
  - 根据 schema type 动态生成格式提示
  - 命令包含 `--dataset train/test` 参数

### CodeAgent Prompts

- `SYSTEM_PROMPT`：CodeAgent 的系统提示词，包含：
  - 角色定位：专注于代码优化的子代理
  - 工作流程：分析 → 优化 → 测试 → 验证
  - `extract-dev` 命令支持：包括 `--standard-entry-ids` 筛选文档、`--key` 筛选字段等参数

### 迭代策略

提示词内置场景策略，包含：

- 冷启动 / 整体准确率低 / 个别字段准确率低
- 回归问题 / 准确率震荡 / 单文档异常
- 接近目标后切 test 验证

并明确在**字段准确率低/回归/单文档异常**场景必须写测试用例覆盖。

### 代码风格

提示词要求：

- 每个字段单独函数
- 复杂逻辑模块化
- 方便 pytest 单元测试

## 运行流程概览

```
用户启动 CLI
  -> 加载 ASA_* 配置
  -> create_workspace
  -> setup_environment
  -> 初始化工具与 PlanNotebook
  -> 启动 Agent
  -> 持续通过 extract-dev / pytest 迭代
```

## CodeAgent 功能

CodeAgent 是一个可选的子代理，用于处理具体的代码优化任务。

### 启用方式

```bash
python -m agentscope_agent run --enable-code-agent --model ... --api-base ... --api-key ...
```

环境变量：
- `ASA_ENABLE_CODE_AGENT=true` - 启用 CodeAgent
- `ASA_CODE_AGENT_MODEL=...` - 指定 CodeAgent 模型（默认同 `ASA_MODEL`）

### 工具接口

CodeAgent 工具函数签名：

```python
async def create_code_agent(
    field: str,                 # 要优化的字段
    hypothesis: str,            # 优化假设
    problem_analysis: str,      # 问题分析
    error_doc_ids: str = "",    # 错误文档ID（逗号分隔）
) -> dict
```

返回格式：
```json
{
  "success": true,
  "changes_summary": "...",
  "tests_written": true,
  "accuracy_improved": true
}
```

### 职责划分

- **ExtractDevAgent**：总体策略、任务分解、问题分析
- **CodeAgent**：具体代码优化、测试编写、局部验证

## 文件写入限制功能

当 API 中转站对大 token 输出响应较慢时，可启用文件写入行数限制模式，引导 Agent 分批写入文件以减少单次生成的 token 量。

### 启用方式

```bash
python -m agentscope_agent run --limit-write-lines --max-write-lines 100 --model ... --api-base ... --api-key ...
```

环境变量：
- `ASA_LIMIT_WRITE_LINES=true` - 启用行数限制模式
- `ASA_MAX_WRITE_LINES=100` - 每次写入最大行数（默认 100）

### 工作原理

启用后，原生 `write_text_file` 和 `insert_text_file` 工具会被带行数限制说明的版本替代：

- 工具描述中明确说明“每次最多写入 N 行”
- Agent 阅读工具描述后会自觉分批写入
- 第一次用 `write_text_file` 覆盖写，后续用 `insert_text_file` 追加

## 多 Agent 架构

### 运行模式

1. **单 Agent 模式**（`--no-supervisor`）
   - 仅 ExtractDevAgent，用户直接交互

2. **Supervisor 模式**（默认）
   - Supervisor 监督 ExtractDevAgent
   - Supervisor 检查进度并给出建议

3. **Supervisor + BusinessAgent 模式**（`--enable-business-agent`）
   - Supervisor 协调 ExtractDevAgent 和 BusinessAgent
   - BusinessAgent 提供业务分析和指导
   - ExtractDevAgent 可通过 `ask_business_agent` 工具主动询问

### Agent 职责

- **Supervisor**：监督整体进度、给出建议、决定是否需要业务分析
- **ExtractDevAgent**：执行具体的提取程序开发和优化
- **BusinessAgent**：分析标准集业务含义、回答业务问题、生成业务指导、触发并发标注
- **LabelingAgent**：独立的文档标注 Agent，由 BusinessAgent 通过 `label_all_documents()` 工具批量创建

### Supervisor 响应解析模式

Supervisor 支持两种响应解析模式，通过 `parse_mode` 参数选择：

#### ParseMode.TEXT_LINE（默认）

从响应文本的最后一行往前扫描，匹配决策标记：
- `[DONE]` - 任务完成
- `[CONTINUE]` - 无需干预
- `[BUSINESS]` - 需要业务分析（仅启用 BusinessAgent 时）

未匹配到决策标记时，返回原文作为建议并记录 warning 日志。

#### ParseMode.STRUCTURED_OUTPUT

使用 AgentScope 的 structured output 功能，通过 Pydantic model 获取结构化决策：

```python
class SupervisorDecision(BaseModel):
    decision: Literal["BUSINESS", "DONE", "CONTINUE", "ADVICE"]
    reason: str | None = None
    advice: str | None = None
```

#### 使用示例

```python
from agentscope_agent.agents import Supervisor, ParseMode

# 默认文本解析模式
supervisor = Supervisor(
    model="...",
    api_base="...",
    api_key="...",
    workspace_path=workspace,
)

# 使用 structured output 模式
supervisor = Supervisor(
    model="...",
    api_base="...",
    api_key="...",
    workspace_path=workspace,
    parse_mode=ParseMode.STRUCTURED_OUTPUT,
)
```

### 信息流

```
Supervisor
    ├── ExtractDevAgent（执行提取优化）
    │       └── ask_business_agent 工具 → BusinessAgent
    └── BusinessAgent（业务分析，Supervisor 触发）
            └── label_all_documents 工具 → LabelingAgent × N（并发标注）
```

### 业务指导文档

启用 BusinessAgent 时，会在 workspace 中生成 `business_guide.md`：

- 包含标准集的业务解释
- 各字段的业务含义和提取规则
- 随着 BusinessAgent 回答问题会自动更新

## 超时控制功能

详细文档：[features/timeout_control.md](./features/timeout_control.md)

### 功能概述

超时控制功能包含两个部分：

1. **超时提醒** - 在运行时间接近限制时，通过 system 消息提醒 agent
2. **强制中断** - 超过时间限制后，调用 agent 的 `interrupt()` 方法强制停止

### 配置参数

```bash
agentscope-agent run \
  --run-timeout 3600 \           # 运行总时长限制（秒）
  --no-timeout-reminder          # 禁用超时提醒（可选）
```

环境变量：
- `ASA_RUN_TIMEOUT` - 运行总时长限制（秒）
- `ASA_TIMEOUT_REMINDER_ENABLED` - 是否启用超时提醒（默认 true）
- `ASA_TIMEOUT_REMINDER_START` - 从剩余多少秒开始提醒（默认 1800）
- `ASA_TIMEOUT_REMINDER_INTERVAL` - 普通提醒间隔（默认 300）
- `ASA_TIMEOUT_COUNTDOWN_THRESHOLD` - 进入倒数模式阈值（默认 300）
- `ASA_TIMEOUT_TEARDOWN` - 超时后缓冲时间（默认 60）

### 工作流程

```
run_timeout 到达 → 提醒继续工作（最后一轮提醒）
                      ↓ 
              teardown 期间等待
                      ↓
run_timeout + teardown → interrupt(ExtractDevAgent) → interrupt(Supervisor)
                      ↓
                  循环退出
```

## 扩展点

- **工具扩展**：可在 `Toolkit` 中新增自定义工具
- **Prompt 扩展**：在 `prompts/` 中更新策略、测试规范
- **Workspace 结构**：可添加更多模板文件（如 `README.md`）
- **测试能力**：可在 `tests/` 目录添加更多 fixtures 或基准样本
- **Hook 扩展**：可在 `hooks/` 中添加自定义 hook（pre_reply/post_reply 等）
