# 系统设计文档

智能文档信息提取系统，基于 LangGraph 构建的迭代优化工作流。

## 模块架构

```
src/
├── agentic_extract/        # Agentic 提取工作流
├── code_executor/          # 代码执行器
├── evaluation_engine/      # 评估引擎（执行+评估组合）
├── evaluator/              # 评估器
├── xdev/                   # extract-dev 重构版 CLI（xdev 命令）
├── extract_agent_common/   # Agent 公共模块（workspace 管理）
├── langchain_llm/          # LLM 客户端
├── memect_apiserver/       # API 服务
├── tree_sitter_cli.py      # Tree-sitter 代码结构分析工具
└── extract_agent/          # 兼容模块（已废弃）
```

### 依赖关系

```
agentic_extract
    ├── xdev
    └── extract_agent_common

evaluation_engine
    ├── code_executor
    └── evaluator

langchain_llm (独立)
memect_apiserver (独立)
xdev (CLI/API，调用 code_executor/evaluator)
```

## 模块说明

### evaluation_engine
组合 code_executor 和 evaluator，提供数据集级别的评估能力。

- **核心功能**：在数据集上执行程序并评估准确率
- **CLI**：不再单独导出 console script；命令行使用 `xdev eval`
- **主要 API**：
  - `EvaluationEngine.from_data_path()` - 创建引擎
  - `evaluate_program()`, `evaluate_program_on_docs()` - 异步评估
  - `evaluate_program_sync()` - 同步评估
- **详细文档**：[evaluation_engine_usage.md](./evaluation_engine_usage.md)

### code_executor
执行提取代码，处理文档数据。

- **核心功能**：执行 Python 提取程序，DocJSON 自动识别 canonical `tree.root` 和 PPX `pages[].objects[]`
- **CLI**：不再单独导出 console script；命令行使用 `xdev run`
- **主要 API**：
  - `execute()` - **统一执行接口**（推荐）
    - 输入源（互斥）：`program` / `program_path` / `workspace`
    - 数据格式（互斥）：`data` / `docjson`
    - 工具注入：`tool_hub=` 显式传入；`code_executor` 不读取 xdev 配置
    - 输出模式：`capture_output=True` 返回 `(result, stdout, stderr)`
  - `batch_execute()` - 批量执行
  - `execute_on_docjson()` - 在 DocJSON 上执行（内部调用 `execute()`）
  - `detect_input_mode()` - 根据函数签名校验 Document-only 输入
- **数据结构**：`Table`, `Cell`（定义在 `code_executor/structure.py`）
- **工具支持**：NER、LLM 抽取、VLM 图片提取等工具（`code_executor/tools/`）
  - `ExtractTool` - 文本结构化提取
  - `LLMSelectTool` - LLM 段落筛选
  - `VLMExtractTool` - VLM 图片信息提取
  - `NerTool` / `NerRegexTool` - NER 工具
- **Document 模型**（`code_executor/document/`）：
  - `Document.get_all_texts(max_items)` - 获取全文段落文本列表
  - `Node.collect_content()` - 递归收集后代节点内容（文本 + TableNode）
  - `TableNode.to_text(max_rows)` - 表格格式化为文本
  - `TableNode.row(i)` / `col(i)` / `cell_at(row, col)` / `iter_rows()` - 表格行列访问
- **详细文档**：[code_executor_usage.md](./code_executor_usage.md)

### evaluator
比较提取结果和标准答案，计算准确率。

- **核心功能**：支持单对象和对象列表的评估
- **CLI**：不再单独导出 console script；通常由 `xdev eval` 间接使用
- **主要 API**：
  - `evaluate()` - 批量评估（自动检测 object / list_of_objects）
  - `compare()`, `compare_objects()`, `compare_list_of_objects()` - 比较函数
  - `ObjectEvaluator`, `ListOfObjectsEvaluator` - 评估器类
  - `EvaluationResult` - 评估结果
- **详细文档**：[evaluator_api_guide.md](./evaluator_api_guide.md)

### extract_agent_common
Agent 公共模块，提供 workspace 管理和共享资源。

- **核心功能**：创建工作目录、初始化 git 仓库、设置环境变量、tiktoken 离线缓存
- **主要 API**：`create_workspace()`, `setup_environment()`, `ensure_tiktoken_cache()`

## CLI 入口汇总

- `tree-sitter-cli` - 代码结构分析工具
- `xdev` - 数据管理、单文档运行、评估 CLI
- `xdev-config` - xdev/agentic-extract 全局配置向导
- `agentic-extract` - agentic_extract 模块 - Agentic 提取工作流
- `pdf-ai-explorer` - DocJSON/PDF 探索工具

## Agent 设计

当前主入口是 `agentic_extract`，旧 AgentScope 相关文档仅作为历史设计参考。

### agentic_extract
Agentic 提取工作流，独立于 agentscope_agent，支持多轮 Agent 循环。

- **核心功能**：自动化提取工作流（运行期编排、Agent 循环、评估反馈、进度事件）
- **CLI**：`agentic-extract run/auto`
- **主要 API**：
  - `run_agentic_extract()` / `run_agentic_extract_async()` - 低层 pure run API
  - `run_agentic_extract_auto()` / `run_agentic_extract_auto_async()` - 高层 one-click API
- **运行反馈**：支持 callback 形式的稳定粗粒度进度事件与 heartbeat
- **结果对象**：返回 `RunResult`，包含 `iteration_count`、每轮/总时长、token usage 等结构化信息
- **Supervisor 决策**：支持 structured output 与文本 JSON 解析两种模式，自动探测+重试
- **评估反馈**：`evaluate` action 将字段级准确率、错误文档 ID 等完整报告反馈给 Supervisor
- **停滞检测**：连续 call_dev 未评估时自动提醒 Supervisor（3 轮建议、6 轮强制）
- **Schema 字段注入**：每次 call_dev 时实时读取当前 schema 字段名注入 task，确保 DevAgent 输出 key 与 schema 一致
- **首轮状态注入**：第 1 轮 Supervisor 消息中附带 workspace 状态（schema 字段、文档数、标注数）
- **ThinkingToTextWrapper**：将 thinking blocks 转为 text blocks，防止 extended thinking 模型循环（`--preserve-thinking`）
- **当前指南**：[agentic_extract_guide.md](./agentic_extract_guide.md)

### xdev
extract-dev 重构版 CLI，统一的开发工具入口。

- **核心功能**：workspace 初始化、数据导入、文档查看、标注检查、单文档运行与评估
- **CLI**：`xdev import-data/list/doc/label-guide/label-status/eval/run/init/sync-pdfs/fix-symlinks`
- **Agent Skills**：推荐使用 [docs/skills/](./skills/) 中的自包含 skill 目录

## 兼容性说明

### extract_agent 兼容模块

旧的 `extract_agent.core.agent_packs` 路径已废弃，请使用 `code_executor`：

```python
# 旧路径（已废弃，会触发 DeprecationWarning）
from extract_agent.core.agent_packs.structure import Table, Cell
from extract_agent.core.agent_packs.get_tools import create_default_tool_hub

# 新路径
from code_executor.structure import Table, Cell
from code_executor.get_tools import create_default_tool_hub
```

## 其他文档

- [project-rules.md](./project-rules.md) - 项目索引（AI Agent 上下文）
- [standard_set_local_storage.md](./standard_set_local_storage.md) - 标准集本地存储格式
- [config_reader_usage.md](./config_reader_usage.md) - 结果文件读取工具
- [refactor_plan_archived.md](./refactor_plan_archived.md) - 重构计划（已完成）
- [evaluator-refactor-plan.md](./evaluator-refactor-plan.md) - evaluator 重构计划
- [test_issues.md](./test_issues.md) - 测试问题记录
- [features/code_quality_tools.md](./features/code_quality_tools.md) - 代码质量工具集成
- [features/vlm_extract_tool.md](./features/vlm_extract_tool.md) - VLM 图片提取工具
- [features/timeout_control.md](./features/timeout_control.md) - **超时控制功能**（运行时间限制、提醒、强制中断）
- [features/label_status_check.md](./features/label_status_check.md) - **标注状态检查**（`xdev label-status` + `relabel_mismatched`）
- [agentic_extract_guide.md](./agentic_extract_guide.md) - **agentic-extract 当前 CLI / Python API 指南**
- [xdev_guide.md](./xdev_guide.md) - **xdev 数据导入、增量维护、同步说明**
- [evaluator_api_guide.md](./evaluator_api_guide.md) - **Evaluator API 使用指南**（compare、evaluate_batch、字段级统计）
