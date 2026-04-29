---
inclusion: always
trigger: always_on
alwaysApply: true
---

# 项目索引

docs/project-rules.md:
这是项目内容的浓缩索引，保持简洁性和时效性。复杂文件以 list 形式列出关键内容。

更新后运行 `make agent-index` 同步到各 Agent 上下文。

## 文档更新准则

### 文件示意
docs/system-design.md 是系统的设计文档
docs/CHANGELOG.md 是一些主要修改的记录文档
docs/features/ 功能特性文档，一般新增的功能的独立文档放这里
docs/archive/ 归档的历史文档

### 准则
- 写务文档时，请先在单独的文档整理新增功能的文档, 这个文档是专注于当前任务的。可以快速的获得当前任务的上下文(需要说明清楚当前任务的前因后果,让人知道要做什么，为什么做这个事情)。然后去更新 docs/system-design.md 及相关文档。然后更新 docs/CHANGELOG.md。
- 更新 docs/system-design.md 时, 注意把长内容通过链接的方式切割出去。

## 项目基础

- 使用 uv 管理环境，执行脚本请使用 `uv run ...`
- 使用 pytest 做测试
- agentic-extract/xdev workspace 会自动初始化 git 仓库并写入默认 `.gitignore`（忽略常见 dotfiles 与缓存文件）

## 相关第三方库文档
- [agentscope](https://doc.agentscope.io/zh_CN/index.html)

## 常见问题索引

| 问题类型 | 参考文档 |
|---------|----------|
| AgentScope 工具函数返回值错误 (TypeError: must return ToolResponse) | `docs/agentscope_tool_guide.md` |

## 模块结构

```
src/
├── agentic_extract/        # Agentic 提取工作流
├── code_executor/          # 代码执行器
├── evaluation_engine/      # 评估引擎（执行+评估组合）
├── evaluator/              # 评估器
├── xdev/                   # extract-dev 重构版 CLI
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

## Console Scripts

`pyproject.toml` 只导出以下命令：

- `tree-sitter-cli` - 代码结构分析工具
- `xdev` - 数据管理、单文档运行、评估 CLI
- `xdev-config` - xdev/agentic-extract 全局配置向导
- `agentic-extract` - Agentic 提取工作流
- `pdf-ai-explorer` - DocJSON/PDF 探索工具

## src/code_executor/

代码执行模块

- `executor.py` - 核心执行逻辑
  - `execute(program, data|docjson, tool_hub=None)` - 执行单个文档的提取
  - `execute_from_workspace(workspace, data)` - 从 workspace 执行
  - `execute_from_workspace_on_docjson(workspace, docjson, pdf_bytes, tool_hub=None)` - 从 workspace 在 docjson 上执行
  - `create_input(docjson, pdf_bytes, mode)` - 创建 `Document` 输入；`mode="flat"` 已不支持
  - `do_extract()` - execute 的别名
- `api.py` - 代码接口
  - `execute_on_docjson(docjson, program, workspace, config, pdf_bytes, tool_hub=None)` - 在 DocJSON 上执行；`config` flat 旧格式已不支持
  - `batch_execute(program, inputs, concurrent)` - 批量执行
  - `batch_execute_on_docjsons(program, docjsons, concurrent, pdf_bytes_list, doc_ids, progress_callback, tool_hub=None)` - 批量在 DocJSON 上执行
  - `batch_execute_workspace_on_docjsons(workspace, docjsons, concurrent, pdf_bytes_list, tool_hub=None)` - 批量 workspace 执行
- `loader.py` - legacy DocJSON 转换
  - `to_plain_article(docjson)` - legacy 纯文本转换；运行时不再推荐
- `structure.py` - 结构化数据类
  - `Table`, `Cell` - 表格数据类
- `run_config.py` - 运行配置
  - `eval_config()`, `EvalResult` - 配置评估
- `utils.py` - 工具函数
  - `get_structure_code()` - 获取结构代码
  - `get_llm_context()` - 获取当前模式的完整上下文文档（给 LLM 看的 Markdown）
- `get_tools.py` - 工具获取
  - `create_default_tool_hub()` - legacy 默认工具中心；新 xdev 路径显式注入 `ToolHub`
- `document/` - Document 模型
  - `Document.from_dict(data)` - 从 canonical/PPX DocJSON 创建
  - `Document.get_node(id)`, `get_nodes_by_page(page)`, `iter_nodes(type_filter)` - 节点查询
  - `Document.get_all_texts(max_items)` - 所有段落文本 flat list
  - `Node.collect_content()` - 递归收集后代内容（str | TableNode）
  - `TableNode.cell_at()`, `row()`, `col()`, `iter_rows()`, `to_text()` - 表格行列访问
- `ner/` - NER 子模块
  - `NERPattern`, `Match`, `StringWithNER`, `NerApi`
- `tools/` - 工具子模块
  - `ToolHub`, `ToolRegistry`, `tool` - 工具注册中心
  - `setup_code_tools()`, `has_default_tool()` - 工具配置
  - `create_default_llm_guide()` - 创建 LLM 工具指南
  - `Settings` - 工具设置
  - `LLMSelectTool`, `ExtractTool`, `NerTool`, `NerRegexTool` - 工具类
  - `VLMExtractTool` - VLM 图片信息提取工具
  - `PDFToImageTool` - PDF 转图片工具

## src/evaluator/

评估器模块

- `core/` - 核心评估逻辑
  - `Evaluator` - 基础评估器类
  - `EvaluationResult` - 评估结果
  - `Schema`, `SchemaField`, `FieldType` - Schema 定义
  - `RecordDetailType`, `FieldDetailType`, `RecordDetailBase` - 详情类型
- `evaluators/` - 评估器实现
  - `ObjectEvaluator`, `ObjectEvaluationResult` - 单对象评估
  - `ListOfObjectsEvaluator`, `ListOfObjectsEvaluationResult` - 对象列表评估
- `standards/` - 标准集管理
  - `StandardSet`, `StandardSetMetadata` - 标准集
  - `StandardSetLoader`, `DirectoryStandardSetLoader` - 加载器
  - `StandardSetManager`, `DatasetEvaluator` - 管理器
- `api.py` - 代码接口
  - `compare()`, `compare_objects()`, `compare_list_of_objects()` - 比较函数
  - `get_evaluator()`, `evaluate_batch()` - 评估函数
  - `get_evaluate_parts()`, `EvaluateParts` - 评估部件
- `cli.py` - CLI 接口
  - 内部 CLI，当前不作为 console script 暴露

## src/evaluation_engine/

评估引擎模块

- `engine.py` - EvaluationEngine 类
  - `from_data_path(data_path, keys, prog_run_concurrent)` - 从本地数据创建
  - `evaluate_program(program, eval_type, keys, std_ids, progress_callback)` - 评估程序
  - `evaluate_program_on_std_ids()` - 在指定文档上评估
  - `ProgressCallback`, `ProgressEvent`, `ProgressStart`, `ProgressDone` - 进度回调类型
- `settings.py` - 配置管理 (pydantic-settings)
  - `Settings` - 配置类，支持环境变量和配置文件
  - 配置文件：`.evaluation_engine.env`
  - 环境变量前缀：`EVALENG_`
  - `EVALENG_PROG_RUN_CONCURRENT` - 程序执行并发数（默认 4）
- `models.py` - 数据模型
  - `Info`, `Standard`, `ExtractedResult`
- `api.py` - 代码接口
  - `evaluate_program(program, data_path, eval_type, keys, std_ids, prog_run_concurrent)` - 异步 API
  - `evaluate_program_on_docs()` - 异步 API
  - `evaluate_program_sync()`, `evaluate_program_on_docs_sync()` - 同步 API
  - `download_dataset()`, `read_program()` - 工具函数
  - `extract_evaluation_data()`, `format_record_detail()` - 格式化函数
- `cli.py` - 内部 CLI，当前不作为 console script 暴露

## docs/

文档

- `system-design.md` - **系统设计文档（总入口）**
- `evaluation_engine_usage.md` - evaluation_engine Python API 指南
- `standard_set_local_storage.md` - 标准集本地存储格式
- `agentscope_agent_design.md` - 历史 AgentScope Agent 设计文档
- `agentscope_tool_guide.md` - **AgentScope 工具函数规范**（工具返回值要求等）
- `config_reader_usage.md` - 结果文件读取工具
- `features/code_quality_tools.md` - 代码质量工具集成（ruff hook、tree-sitter CLI）
- `features/vlm_extract_solution.md` - **VLM 提取方案**（入口文档）
- `features/vlm_tools.md` - VLM 工具集 API（VLMExtractTool、PDFToImageTool）
- `features/pdf_data_flow.md` - PDF 数据流
- `features/tool_strategies.md` - 策略提示词设计
- `features/extraction_strategies.md` - **提取策略增强**（Document 模型新方法 + 策略重写）
- `features/code_tools_context.md` - 代码工具上下文机制
- `features/redirect_stdout_thread_safety.md` - **redirect_stdout 线程安全问题**（待修复 TODO）
- `features/timeout_control.md` - **超时控制功能**（运行时间限制、提醒、强制中断）
- `features/cli_dependencies.md` - **CLI 依赖清单**（项目依赖 vs 系统工具）
- `features/label_status_check.md` - **标注状态检查**（`xdev label-status` + `relabel_mismatched`）
- `agentic_extract_guide.md` - **agentic-extract 当前 CLI / Python API 指南**
- `xdev_guide.md` - **xdev 数据导入与增量维护指南**
- `evaluator_api_guide.md` - **Evaluator API 使用指南**

## src/agentic_extract/

Agentic 提取工作流（独立于 agentscope_agent）

- `api.py` - 对外 Python API
  - `run_agentic_extract()` / `run_agentic_extract_async()` - 低层 pure run
  - `run_agentic_extract_auto()` / `run_agentic_extract_auto_async()` - 高层 one-click
- `runner.py` - 主编排器（setup / probe / iteration / finalize）
- `runtime.py` - 运行期事件、heartbeat、token 统计
- `types.py` - `RunResult` / `IterationResult` / `ProgressEvent` / `PrepareSpec` 等公共契约
- `workspace.py` - workspace readiness、初始化与状态汇总
- `prepare.py` - 高层 auto 入口的数据准备判定与 bootstrap
- `supervisor.py` - Supervisor 决策解析、structured probe、重试
- `evaluate.py` - `xdev eval` 调用与结果解析
- `agents.py` - Agent 实现
- `tools.py` - 工具注册
- `hooks.py` - Hook（ruff check 等）
- `model_factory.py` - 模型工厂
- `config.py` - 配置管理
- `state.py` - 状态管理
- `prompts/` - Supervisor / Business / Dev 提示词素材
- `labeling/` - 标注子模块
- `cli.py` - CLI 接口
  - `run`, `auto` 命令

## docs/skills/

Agent skill 文档源目录。每个目录都应尽量自包含，便于直接复制给外部 agent 使用。

- `xdev/` - workspace 数据准备、schema、标注、评估
- `agentic-extract/` - agentic loop、auto、Python API、progress events
- `pdf-ai-explorer/` - DocJSON/PDF 长文档导航

## src/xdev/

extract-dev 重构版 CLI

- `cli.py` - CLI 入口
  - `import-data` - 数据导入（支持 `--add-pdf`, `--reparse`, `--std-ids`, `--sync`, `--skip-exist`）
  - `list` - 列出文档
  - `doc` - 查看文档内容
  - `label-guide` - 标注指南
  - `label-status` - 标注状态检查
  - `eval` - 评估
  - `run` - 执行提取
  - `init` - 初始化 workspace
  - `sync-pdfs` - 同步 PDF
  - `fix-symlinks` - 修复符号链接
- `api.py` - 代码接口
- `evaluation.py` - 评估逻辑
- `import_data.py` - 数据导入
- `config.py` - 配置管理
- `workspace.py` - Workspace 管理
- `models.py` - 数据模型
  - `generate_html_report(result)` - 生成 HTML 报告字符串
  - `save_html_report(result, path)` - 保存 HTML 报告到文件
  - `extract_from_docjson(docjson, program, workspace, config, pdf_bytes)` - 独立提取函数
  - `SafeJSONEncoder` - 安全 JSON 编码器（支持 Ellipsis, set, bytes, inf, nan）
  - 工具函数: `get_article()`, `get_standard()`, `get_schema()`, `list_doc_ids()`, `get_doc_data()`
- `html_report.py` - HTML 报告生成（支持双栏布局 + PDF 预览）
  - `generate_html_report(result_with_meta, base_url)` - 生成 HTML 字符串
  - `save_html_report(result_with_meta, path, base_url)` - 保存到文件
  - PDF 预览通过 DatasetApp API 获取 pdf_link
- `config.py` - 配置管理 (pydantic-settings)
  - `ExtractDevSettings` - 环境变量配置类
  - 环境变量: `EXTRACT_SET_ID`, `EXTRACT_BASE_URL`, `EXTRACT_PROGRAM`

## src/extract_agent_common/

Agent 公共模块（workspace 管理）

- `workspace.py` - Workspace 创建与管理
  - `create_workspace(workspace)` - 创建或复用工作目录
  - `setup_environment(workspace_path, chdir, enabled_tools)` - 设置环境变量
    - `enabled_tools`: 启用的代码工具列表，可选值: `ner_regex_tool`, `extract`, `llm_select`, `vlm_extract`, `pdf_to_image`

## src/agentscope_agent/

AgentScope Agent

- `workflow.py` - 主流程编排
  - `run_extract_dev_agent()` - 运行 Agent
  - `run_agent_async()` - 异步主流程（支持多种模式）
  - `commit_workspace()` - 自动提交工作区变更
- `cli.py` - CLI 入口
  - 子命令: `run`（启动 Agent）, `test`（测试 API 连通性）
  - 环境变量: `ASA_MODEL`, `ASA_API_BASE`, `ASA_API_KEY`, `ASA_SET_ID`, `ASA_RUN_TIMEOUT`, `ASA_TIMEOUT_REMINDER_ENABLED`, `ASA_ENABLED_TOOLS`
  - run 可选参数: `--set-id`, `--studio-url`, `--supervisor-model`, `--max-iterations`, `--target-accuracy`, `--no-supervisor`, `--reset`, `--api-timeout`, `--run-timeout`, `--no-timeout-reminder`, `--enabled-tools`
- `model_factory.py` - 模型工厂
  - `test_connection()` - 测试 API 连通性
- `config.py` - 配置管理
- `model_factory.py` - 模型工厂（支持 `gemini/xxx`, `openai/xxx` 前缀）
- `prompts/` - Prompt 定义
  - `extract_dev.py` - ExtractDevAgent 提示词
  - `supervisor.py` - Supervisor 提示词（支持 with/without BusinessAgent）
  - `business.py` - BusinessAgent 提示词
  - `code_agent.py` - CodeAgent 提示词
  - `strategies.py` - 策略提示词（`STRATEGIES` 常量）
- `tracking/` - 监控统计模块
  - `TokenStats` - Token 统计
  - `TokenTrackingModelWrapper` - 模型包装器
- `state/` - 状态管理模块
  - `StateSaver` - 防抖保存器
  - `SessionManager` - Session 管理
- `agents/` - Agent 实现模块
  - `create_extract_dev_agent()` - ExtractDevAgent 工厂
  - `create_code_agent_tool()` - CodeAgent 工具创建（可选）
  - `Supervisor` - 统一的监督者类（支持可选 BusinessAgent，支持 `parse_mode` 解析模式）
  - `ParseMode` - 响应解析模式枚举（`TEXT_LINE`/`STRUCTURED_OUTPUT`）
  - `SupervisorDecision` - Pydantic model（用于 structured output）
  - `BusinessAgent` - 业务分析 Agent 类
- `tools/` - 工具模块
  - `register_file_tools()` - 注册文件写入工具（支持可选行数限制）
  - `create_file_tools()` - 创建文件工具
  - `ask_business_agent()` - 询问业务 Agent 工具
  - `set_business_agent()` / `get_business_agent()` - BusinessAgent 全局引用
  - **注意**: 工具函数必须返回 `ToolResponse`，详见 `docs/agentscope_tool_guide.md`
- `hooks/` - Hook 模块
  - `register_ruff_check_hook()` - 注册 ruff check hook（写入 .py 文件后自动检查）
  - `register_timeout_reminder_hook()` - 注册超时提醒 hook
- `timeout.py` - 超时控制模块
  - `TimeoutReminder`, `TimeoutReminderConfig` - 超时提醒管理
  - `timeout_monitor()` - 超时监控协程（强制中断）
  - `set_timeout_reminder()`, `get_timeout_reminder()` - 全局访问
- `prompts/tools/` - 工具 Prompt
  - `ruff.py`, `tree_sitter.py`, `mypy.py`, `pytest_cov.py`

### 模型配置注意事项

- Gemini 模型通过 API 中转站时，需要特殊处理（base_url 移除 `/v1`，timeout 单位转换，代理配置）
- Gemini thinking 模型（如 `gemini-3-flash-preview-thinking-*`）不支持（AgentScope 不处理 `thought_signature`）
- 推荐使用 `gemini/gemini-2.0-flash`

## src/llm_standard_generator/

LLM 标准生成器（用大模型读取文档生成标准集数据）

- `generator.py` - 主入口
  - `generate_standards(documents, schema, concurrency)` - 批量生成标准集
  - `DocumentInput` - 文档输入数据类
  - `StandardResult` - 标准集结果数据类
- `llm_extractor.py` - LLM 提取器
- `schema_converter.py` - Schema 转换器
- `config.py` - 配置

<skills_system priority="1">

## Available Skills

<!-- SKILLS_TABLE_START -->
<usage>
When users ask you to perform tasks, check if any of the available skills below can help complete the task more effectively. Skills provide specialized capabilities and domain knowledge.

How to use skills:
- Invoke: `npx openskills read <skill-name>` (run in your shell)
  - For multiple: `npx openskills read skill-one,skill-two`
- The skill content will load with detailed instructions on how to complete the task
- Base directory provided in output for resolving bundled resources (references/, scripts/, assets/)

Usage notes:
- Only use skills listed in <available_skills> below
- Do not invoke a skill that is already loaded in your context
- Each skill invocation is stateless
</usage>

<available_skills>

<skill>
<name>algorithmic-art</name>
<description>Creating algorithmic art using p5.js with seeded randomness and interactive parameter exploration. Use this when users request creating art using code, generative art, algorithmic art, flow fields, or particle systems. Create original algorithmic art rather than copying existing artists' work to avoid copyright violations.</description>
<location>project</location>
</skill>

<skill>
<name>brand-guidelines</name>
<description>Applies Anthropic's official brand colors and typography to any sort of artifact that may benefit from having Anthropic's look-and-feel. Use it when brand colors or style guidelines, visual formatting, or company design standards apply.</description>
<location>project</location>
</skill>

<skill>
<name>canvas-design</name>
<description>Create beautiful visual art in .png and .pdf documents using design philosophy. You should use this skill when the user asks to create a poster, piece of art, design, or other static piece. Create original visual designs, never copying existing artists' work to avoid copyright violations.</description>
<location>project</location>
</skill>

<skill>
<name>doc-coauthoring</name>
<description>Guide users through a structured workflow for co-authoring documentation. Use when user wants to write documentation, proposals, technical specs, decision docs, or similar structured content. This workflow helps users efficiently transfer context, refine content through iteration, and verify the doc works for readers. Trigger when user mentions writing docs, creating proposals, drafting specs, or similar documentation tasks.</description>
<location>project</location>
</skill>

<skill>
<name>docx</name>
<description>"Comprehensive document creation, editing, and analysis with support for tracked changes, comments, formatting preservation, and text extraction. When Claude needs to work with professional documents (.docx files) for: (1) Creating new documents, (2) Modifying or editing content, (3) Working with tracked changes, (4) Adding comments, or any other document tasks"</description>
<location>project</location>
</skill>

<skill>
<name>frontend-design</name>
<description>Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks to build web components, pages, artifacts, posters, or applications (examples include websites, landing pages, dashboards, React components, HTML/CSS layouts, or when styling/beautifying any web UI). Generates creative, polished code and UI design that avoids generic AI aesthetics.</description>
<location>project</location>
</skill>

<skill>
<name>internal-comms</name>
<description>A set of resources to help me write all kinds of internal communications, using the formats that my company likes to use. Claude should use this skill whenever asked to write some sort of internal communications (status reports, leadership updates, 3P updates, company newsletters, FAQs, incident reports, project updates, etc.).</description>
<location>project</location>
</skill>

<skill>
<name>mcp-builder</name>
<description>Guide for creating high-quality MCP (Model Context Protocol) servers that enable LLMs to interact with external services through well-designed tools. Use when building MCP servers to integrate external APIs or services, whether in Python (FastMCP) or Node/TypeScript (MCP SDK).</description>
<location>project</location>
</skill>

<skill>
<name>pdf</name>
<description>Comprehensive PDF manipulation toolkit for extracting text and tables, creating new PDFs, merging/splitting documents, and handling forms. When Claude needs to fill in a PDF form or programmatically process, generate, or analyze PDF documents at scale.</description>
<location>project</location>
</skill>

<skill>
<name>pptx</name>
<description>"Presentation creation, editing, and analysis. When Claude needs to work with presentations (.pptx files) for: (1) Creating new presentations, (2) Modifying or editing content, (3) Working with layouts, (4) Adding comments or speaker notes, or any other presentation tasks"</description>
<location>project</location>
</skill>

<skill>
<name>skill-creator</name>
<description>Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Claude's capabilities with specialized knowledge, workflows, or tool integrations.</description>
<location>project</location>
</skill>

<skill>
<name>slack-gif-creator</name>
<description>Knowledge and utilities for creating animated GIFs optimized for Slack. Provides constraints, validation tools, and animation concepts. Use when users request animated GIFs for Slack like "make me a GIF of X doing Y for Slack."</description>
<location>project</location>
</skill>

<skill>
<name>template</name>
<description>Replace with description of the skill and when Claude should use it.</description>
<location>project</location>
</skill>

<skill>
<name>theme-factory</name>
<description>Toolkit for styling artifacts with a theme. These artifacts can be slides, docs, reportings, HTML landing pages, etc. There are 10 pre-set themes with colors/fonts that you can apply to any artifact that has been creating, or can generate a new theme on-the-fly.</description>
<location>project</location>
</skill>

<skill>
<name>web-artifacts-builder</name>
<description>Suite of tools for creating elaborate, multi-component claude.ai HTML artifacts using modern frontend web technologies (React, Tailwind CSS, shadcn/ui). Use for complex artifacts requiring state management, routing, or shadcn/ui components - not for simple single-file HTML/JSX artifacts.</description>
<location>project</location>
</skill>

<skill>
<name>webapp-testing</name>
<description>Toolkit for interacting with and testing local web applications using Playwright. Supports verifying frontend functionality, debugging UI behavior, capturing browser screenshots, and viewing browser logs.</description>
<location>project</location>
</skill>

<skill>
<name>xlsx</name>
<description>"Comprehensive spreadsheet creation, editing, and analysis with support for formulas, formatting, data analysis, and visualization. When Claude needs to work with spreadsheets (.xlsx, .xlsm, .csv, .tsv, etc) for: (1) Creating new spreadsheets with formulas and formatting, (2) Reading or analyzing data, (3) Modify existing spreadsheets while preserving formulas, (4) Data analysis and visualization in spreadsheets, or (5) Recalculating formulas"</description>
<location>project</location>
</skill>

</available_skills>
<!-- SKILLS_TABLE_END -->

</skills_system>
