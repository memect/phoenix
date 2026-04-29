# Changelog

本文档记录项目的主要修改。

## 2026-04-27

### 重构 — DocJSON 自动识别与 xdev ToolHub 注入

- 版本号切换到 `0.4.0`
- 新增 DocJSON adapter，自动识别 canonical `tree.root` 与 PPX `pages[].objects[]`
- PPX DocJSON 会按 Markdown 标题层级还原 `title -> section` 文档树
- `Document.from_dict()`、`create_input()` 和 DocJSON 执行 API 会防御性 normalize
- DocJSON 执行进入 Document-only：flat/article/config 旧路径改为清晰失败
- `code_executor` 支持显式 `tool_hub=`，但不自动读取 xdev 配置
- `xdev run` / `xdev eval` / Python API 会自动读取 xdev 配置、构造单个 ToolHub 并注入 `extract(document, tool_hub)`
- workspace 模板、prompt、skill 和主要文档改为推荐显式 ToolHub 注入写法
- console scripts 收敛为 `tree-sitter-cli`、`xdev`、`xdev-config`、`agentic-extract`、`pdf-ai-explorer`
- 移除 `pyproject.toml` 中的私有依赖解析 index，`pdf-ai-explorer` 改为仓库本地 wheel source

## 2026-04-24

### 修复 — DeepSeek thinking/tool-call 兼容

- `agentic-extract` 现支持显式 `deepseek/<model_name>` 前缀
- 官方 DeepSeek OpenAI 兼容端点会自动切换到 `DeepSeekMultiAgentFormatter`
- 避免在 DeepSeek chat.completions 路径上把 thinking 降级成普通文本，从而保留 `reasoning_content`
- 新增 `test_model_factory.py` 回归测试，覆盖 formatter 选择和 `preserve_thinking` 保护逻辑

### 修复 — structured output 探测兼容 DeepSeek JSON 模式

- `probe_structured_output()` 的探测 prompt 改为显式包含 `json`
- 避免 DeepSeek 因 `response_format={"type":"json_object"}` 且 prompt 未提及 json 而误报 probe 失败
- 新增对应 supervisor 回归测试

### 改进 — DeepSeek 默认配置与文档示例

- 工作区与全局 `agentic-extract` 配置中的标注模型默认切到 `deepseek-v4-flash`
- `xdev` / 提取链路相关示例统一改为 `deepseek-v4-flash`
- 主 `agentic-extract` 模型仍保留 `deepseek-v4-pro` 的推荐搭配
## 2026-04-23

### 新增 — agentic-extract 运行事件落盘与详细 agent 消息

- 默认将运行事件写入 `workspace/.agent_state/events.jsonl`
- `RunRecorder` 的阶段、迭代、step、heartbeat、完成/失败事件会落成 JSONL
- 基于 AgentScope hook 增加详细 agent 事件：`agent_call_started`、`agent_message`、`agent_call_completed`
- `agentic-extract auto` 路径补充 setup / prepare 相关事件，避免事件流只覆盖 run 主循环
- 新增 `events.py` 事件写入模块与配套测试，`tests/agentic_extract` 全量通过

### 新增 — 维护者 release-process skill

- 新增仓库本地 skill：`docs/skills/release-process/`
- 新增随包发布版 skill：`src/agentic_extract/skills/release_process/SKILL.md`
- `README.md` 与 `docs/release_process.md` 现在直接指向 release-process skill
- `xdev export-skills` 新增导出 `release_process/SKILL.md`

## 2026-04-20

### 改进 — agentic-extract CLI 预算控制与文档整理

- `agentic-extract` 默认预算改为 `standard`：`max_iterations=10`、`agent_max_iters=25`
- 新增 `--budget fast`：`max_iterations=10`、`agent_max_iters=10`
- 新增 `--budget full`：`max_iterations=50`、`agent_max_iters=100`
- 支持继续通过 `--max-iterations`、`--agent-max-iters`、`--supervisor-max-iters`、`--business-max-iters`、`--dev-max-iters` 显式覆盖预算
- CLI 启动时会输出预算摘要，方便确认本次运行的生效预算
- Supervisor 默认模式切换为 `simple`
- 新增聚焦 `run` / `auto` / budget 的 CLI 文档：`docs/agentic_extract_cli.md`

### 新增 — `xdev-config` 全局配置向导

- 新增独立命令 `xdev-config`
- 支持交互式、非交互式、混合补全和 `--show` 查看模式
- 同时写入 `~/.config/agentic-extract/config.json` 与 `~/.config/xdev/config.json`
- `xdev` 的 `extract_tool` 和 `llm_select_tool` 会同步使用同一套 `extract-llm`
- 新增 CLI 测试，覆盖打码展示、必填校验、增量更新与交互补全

### 改进 — PDF 解析默认使用 PPX CLI

- 默认 PDF → DocJSON 路径改为调用本机 `ppx parse`，不再依赖 `memect_api_base`
- 批量 PDF 解析统一走 `ppx parse <dir> --workers N`，新增 `pdf_parse_concurrent` / `XDEV_PDF_PARSE_CONCURRENT` 控制文件级并发，默认 `1`
- PPX 输出写入临时目录，xdev 只保存最终 `.xdev/data/docjson/*.json` 与 `.xdev/data/pdf/*.pdf`

### 改进 — `xdev run` 支持直接运行单个 PDF / DocJSON

- `xdev run` 新增 `--pdf` 与 `--docjson` 选项
- 现在支持三种单次提取输入：`doc_id`、单个 PDF、单个 DocJSON
- `doc_id` / `--pdf` / `--docjson` 三者必须且只能选一个
- 单个 PDF 会先通过本机 `ppx parse` 解析成 DocJSON，再复用现有 workspace 执行链

### 改进 — xdev 默认提取长度与配置展示

- `extract_tool` 与 `llm_select_tool` 的默认 `max_content_length` 统一为 `50000`
- `xdev-config` 的 `--show` 和写入前 summary 现在会展示 `base_url`、`concurrent`、`pdf_parse_concurrent`、`memect_api_base`、`max_content_length`，并补充 `llm_select_max_content_length`
- `xdev-config` 写入 `~/.config/xdev/config.json` 时，如果缺少这些默认字段，会自动补齐 `base_url`、`concurrent`、`pdf_parse_concurrent`、`memect_api_base`、`extract_tool.max_content_length` 与 `llm_select_tool.max_content_length`

### 改进 — `extract-agent` 直接暴露 `pdf-ai-explorer` CLI

- `pyproject.toml` 的 `project.scripts` 新增 `pdf-ai-explorer = "pdf_ai_explorer.cli:app"`
- 现在安装 `extract-agent` 时，会一并暴露 `pdf-ai-explorer` 命令，减少二次安装步骤
- 更新安装文档，默认安装路径改为只安装 `extract-agent`

## 2026-04-15

### 重构 — agentic-extract 公共 Python API、运行期事件与状态落盘

- 新增低层 pure run API：`run_agentic_extract()` / `run_agentic_extract_async()`
- 新增高层 one-click API：`run_agentic_extract_auto()` / `run_agentic_extract_auto_async()`
- 新增公共类型：`RunResult`、`IterationResult`、`ProgressEvent`、`TokenUsage`、`PrepareSpec`
- 新增 callback 形式的稳定粗粒度进度事件与 heartbeat，运行中可持续接收 phase / iteration / step / heartbeat 进度
- 新增运行期 recorder 与 token usage 聚合，结果中可获得 `iteration_count`、每轮迭代时长、总迭代时长、总运行时长，以及 cache / reasoning token 明细
- CLI `agentic-extract run` 已切换为低层 pure run 适配层
- CLI 新增 `agentic-extract auto`，负责 bootstrap + run
- `RunRequest` / `run_agentic_extract_request*()` 已标记为兼容层，不再推荐给新调用方
- `state.py` 的迭代记录已扩展为结构化字段：`started_at`、`finished_at`、`duration_sec`、`token_usage`、`summary`、`error`
- 删除旧入口 `src/agentic_extract/loop.py`
- 新增并更新测试：`test_api.py`、`test_runtime.py`、`test_usage.py`、`test_runner.py`、`test_cli.py`、`test_state.py`
- 新增当前使用文档：[agentic_extract_guide.md](./agentic_extract_guide.md)

## 2026-04-14

### 修复 — xdev eval 评估结果属性透传

- 修复 `xdev.evaluation_result.EvaluationResult` 未透传底层评估对象属性的问题
- `xdev eval` 现在可以正常访问 `overall_accuracy`、`total_records`、`field_stats` 等属性并打印完整评估报告
- 为 `run_evaluation()` 补充集成测试，覆盖 `field_stats` 和 `total_records` 的兼容访问

### 删除 extract_dev 和 llm_standard_generator，迁移功能到 xdev

**删除模块**：
- `extract_dev/` - 旧评估模块，功能已迁移到 `xdev`
- `llm_standard_generator/` - 未使用的 LLM 标准生成模块

**新增 xdev 功能**：
- `xdev/extract.py`：`extract_from_docjson` 支持 workspace/program/config 三种模式
- `xdev/evaluation_result.py`：`EvaluationResult` 替代 `EvaluationResultWithMetadata`
- `xdev/html_report.py`：HTML 报告生成（PDF 链接从 manifest 读取，无则留空）
- `xdev/evaluation.py`：`run_evaluation` 返回 `EvaluationResult`

**版本**：0.2.1 → 0.3.0

## 2026-04-07

### 重构 — 删除冗余模块并清理依赖

**删除模块**：
- `agentscope_agent/` - 已被 `agentic_extract` 完全替代，删除全部 44 个文件
- `fact_extract/` - 未使用的事实提取 pipeline，删除全部 28 个文件
- `simple_workflow/` - 未使用的工作流模块，删除全部 28 个文件

**依赖清理**：
从 `pyproject.toml` 移除 14 个未使用的依赖：
- Web 框架：`fastapi`, `uvicorn`, `websockets`, `python-multipart`
- 数据库：`sqlalchemy`, `alembic`, `psycopg2-binary`
- 任务队列：`celery`, `flower`, `redis`
- 其他：`openpyxl`, `fact-analyze`, `pysbd`

**Bug 修复**：
- 修复 `scripts/agentic_batch.sh` 中的 API 认证冲突问题：在子进程中 unset `ANTHROPIC_*` 环境变量，避免与 `.agentic-extract.json` 配置文件中的 `api_key` 冲突

**影响**：
- 代码量减少：删除 25,705 行，新增 2,267 行（主要是 uv.lock 更新）
- 包体积减少：wheel 从 2.2MB 降至 1.9MB
- 核心模块 `agentic_extract` 功能不受影响，所有测试通过

## 2026-04-02

### 改进 — agentic-extract BusinessAgent prompt 重写 + 异常处理 + Supervisor simple 模式

- **BusinessAgent prompt 重写**：新增"每次回复必须包含工具调用"强制规则，明确 `business_guide.md` 和标注文件的位置与写入方式（含 `write_text_file` 示例），禁止读取 `program.py`/`tests/`（DevAgent 职责），禁止写 python 脚本解析 docjson
- **Agent 异常处理**：BusinessAgent 和 DevAgent 调用增加 try/except，异常时打印错误信息并继续循环，避免静默中断
- **Supervisor simple 模式**：新增 `--supervisor simple` CLI 选项，Supervisor 不注册任何工具，仅做纯决策路由；适用于 reasoning 模型（如 gpt-5.4）避免 think 模式下工具调用不稳定
- **Supervisor task 描述优化**：task 改为直接指令形式（"运行 xdev doc 查看文档，创建 business_guide.md"），禁止使用"请业务侧提供…"等间接表达
- **Agent 状态目录迁移**：agent memory 从 `logs/agent_memory/` 迁移至 `.agent_state/`，避免与运行日志混淆
- **xdev doc 长文档提示优化**：pdf-ai-explorer 命令示例补全（outline/search/read/content），修正参数顺序
- **xdev SKILL.md 精简**：移除 `--data-dir` 全局选项描述（workspace 内工作时无需指定）

## 2026-03-20

### 改进 — agentic-extract supervisor loop 优化

解决 Agent 不查看真实文档、不校验字段名、评估信息丢失、无停滞检测等问题：

- **评估结果结构化**：`_run_xdev_eval` 解析完整 xdev eval 报告（字段级准确率、错误文档 ID、字段平均），`EvaluationSnapshot` 新增 `field_average`、`error_count`、`error_doc_ids`、`field_accuracies`、`report_text` 字段
- **evaluate action 反馈增强**：Supervisor 收到字段级准确率 + ⚠ 标记 + 错误文档列表，而非仅 "准确率 X%"
- **停滞检测**：连续 call_dev 未评估计数器，3 轮建议评估，6 轮强制提醒
- **Schema 字段注入**：每次 call_dev 实时读取当前 schema 字段名注入 task（schema 可能被 BusinessAgent 更新）
- **首轮 workspace 状态注入**：第 1 轮 Supervisor 消息包含 schema 字段、文档数、标注数、program.py 存在性
- **Supervisor prompt 增强**：新增首轮要求（先了解数据再决策）、task 内容规范（包含具体字段/文档ID）、停滞提醒说明
- **迭代摘要增强**：`get_recent_summary` 从 3 轮扩展到 5 轮，追加准确率趋势

### 改进 — agentic-extract supervisor 决策增强
- Supervisor 决策解析重构：支持单行 JSON、markdown 代码块、多行 JSON 三种格式
- 新增 structured output 探测：启动时自动测试模型是否支持 structured output（`_probe_structured_output`），可用时优先使用
- 决策重试机制：文本解析失败后自动发送格式提示并重试（最多 2 次）
- `SupervisorDecision` 改用 `Literal` 类型约束 action 取值，模糊匹配纠正大小写
- Supervisor prompt 精简：两阶段工作流（调查→决策）+ 格式提醒追加到 system prompt
- Business/Dev Agent prompt 新增「工作方式」指引（读取→修改→验证，避免重复读文件）
- 新增 `--preserve-thinking` 选项：`ThinkingToTextWrapper` 将 thinking blocks 转为 text blocks，防止 extended thinking 模型循环
- 新增依赖：`fact-analyze`（本地 editable 包）

### 新增 — fact-extract analyze pipeline
- 新增 `analyze` CLI 命令：委托 `fact_analyze` 包，执行实体→事件→关系→时间线全流程
- 新增 `document.py`：输入适配器，PDF/docjson/纯文本 → document.json 格式
- 新增 `entity_identify.py`：实体识别+消歧 → entities.json
- 新增 `entity_attributes.py`：实体属性提取 → entity_attributes.json
- 新增 `entity_relations.py`：段落级实体关系提取 → entity_relations.json
- 新增 `event_extract.py`：事件提取 → events.json
- 新增 `event_relations.py`：事件关系发现 → event_relations.json
- 新增 `timeline.py`：纯规则时间线合成 → timeline.json
- 新增 `_batch.py`：共享的按字数切分 batch 工具
- `auto_section.py` 新增 `system_prompt` 和 `intermediate_dir` 参数

## 2026-03-16

### 改进 — fact-extract section-mode 与默认后端调整
- `--auto-section` 标志替换为 `--section-mode` 选项，支持三种模式：
  - `docjson`（默认）：按原始 section 节点合并文本
  - `line`：每个 textline 作为独立 evidence item
  - `auto`：LLM 自动分段（等同原 `--auto-section`）
- `evidence.py` 中 `extract_evidence_items()` 新增 `section_mode` 参数，重构为统一分发逻辑
- 新增 `_split_section_lines()` 函数，支持行级粒度的 evidence 拆分
- 默认 extractor-backend 从 `agentic` 改为 `llm-once`（`extract-task`/`run-workers`/`run` 三处）
- 删除 `src/fact_extract/SKILL.md`（已迁移到本地 skills 目录）

### 改进 — tiktoken 离线缓存迁移到公共模块
- 将 tiktoken 缓存文件从 `agentscope_agent/data/` 迁移到 `extract_agent_common/data/tiktoken/`
- 新增 `extract_agent_common/tiktoken_cache.py`：`ensure_tiktoken_cache()` 使用 `importlib.resources` 定位缓存目录
- `agentic_extract/cli.py` 和 `agentscope_agent/cli.py` 统一调用此函数，避免重复代码
- 删除 `agentscope_agent/data/` 目录（缓存已迁移）

## 2026-03-12

### 新增 — b2u 自底向上层级聚合
- 新增 `b2u.py`：将 summaries.json 递归聚合为树形层级结构 `hierarchy.b2u.json`
- 每轮 LLM 并发分组（滑动窗口，默认 32 并发），轮间串行，直到收敛为一个 root
- 只合并相邻 items，保持文本线性顺序；每个 group 自带 summary
- CLI: `fact-extract b2u --summaries <path> --model/--api-base/--api-key`
- 详细文档：[features/b2u_hierarchy.md](features/b2u_hierarchy.md)

### 新增 — segment 独立 pipeline
- 新增 `segmenter.py`：独立文本切分 pipeline（不依赖 plan/task 结构）
- 输入支持 `.txt`（按行）与 `.json`（docjson `tree.root.children[].data.textlines` 格式）
- 滑动窗口断点检测改为**全并发**（所有窗口同时提交 `ThreadPoolExecutor`，默认 32 并发）
- 输出 `chunks.json`（chunk_id + sentences）+ `breakpoints.json`，作为 summary/enrich 的输入
- CLI: `fact-extract segment --input <file> --output-dir <dir> --max-workers 32`
- 详细文档：[features/segment_pipeline.md](features/segment_pipeline.md)

### 改进 — enrich 支持 chunks 输入
- `enricher.py` 新增 `enrich_chunks()`：直接对 `chunks.json` 进行实体/属性/关系/事件抽取
- CLI: `fact-extract enrich --chunks <path>` / `--manifest <path>`（互斥）

### 新增 — enrich 后处理
- 新增 `enricher.py`：对 manifest 中每条 fact 提取实体/属性/关系/事件四类结构化知识
- LLM 并发提取（默认 32），每条完成立即写入 `enriched/<id>.json`，支持断点续跑
- 全部完成后汇总为 `manifest.enriched.json`
- CLI: `fact-extract enrich --manifest <path> --model/--api-base/--api-key`
- 详细文档：[features/enrich_postprocess.md](features/enrich_postprocess.md)

### 新增 — segmented extractor backend
- 新增 `segmented` 提取后端：pysbd 句子切分 → LLM 语义断点检测 → 按语义边界分块 → 逐块 LLM 摘要
- 一个语义块 = 一条 fact，断点检测决定事实粒度
- source_ids 直接对应 chunk 内的句子级 evidence（无需 LLM 返回引用）
- 32 并发 chunk 摘要，中间结果实时保存（`segmented_breakpoints.json`、`segmented_summaries.json`）
- 新增 `_text.py: split_sentences_pysbd()` 函数，支持中文句子切分
- CLI（`extract-task`、`run-workers`、`run`）`--extractor-backend` 支持 `segmented` 选项
- 新增依赖 `pysbd>=0.3.4`
- 详细文档：[features/segmented_extractor.md](features/segmented_extractor.md)

### 改进 — pdf-ai-explorer 去除命令行依赖
- `pdf.py`：直接使用 `PDFAITool` Python API（`get_outline` / `read_page`），去除 subprocess 依赖
- `agent_tools.py`：使用 `typer.testing.CliRunner` 透传子命令，去除 subprocess 依赖
- 不再需要 `pdf-ai-explorer` 在 PATH 中或 `uvx` 可用

### 改进 — planner 页码确认机制
- agentic planner prompt 新增「页码确认原则」：写入任务前每个 groups 必须是已确认的实际物理页码
- 大纲缺失或页码可疑时，通过正则搜索章节标志（如 `第.{1,3}回`）一次性获取所有分割点实际页码
- LLM planner constraints 同步补充章节标志推断规则

## 2026-03-11

### 改进 — agentic-extract 上下文压缩兼容性修复
- 压缩模型使用独立的 `stream=False` 实例，避免流式解析在 API 代理上报错
- 新增 `PlainJsonModelWrapper`：将 structured output 请求转为纯文本 JSON 解析，兼容不支持 OpenAI structured output 的 API 代理（如 Claude via OpenAI 兼容接口）

### 改进 — agentic-extract CLI 新增选项
- `--max-context-length`：最大上下文长度（token），控制压缩触发阈值
- `--compression-keep-recent`：压缩时保留的最近消息数
- 支持项目级配置文件 `.agentic-extract.json`（已加入 `.gitignore`）

### 改进 — xdev eval 进度打印与耗时统计
- `batch_execute_on_docjsons` 新增 `doc_ids` 和 `progress_callback` 参数
- `xdev eval` 执行过程中逐个打印完成进度（使用 `sys.__stdout__` 绕过 redirect_stdout 线程安全问题）
- 执行结束后打印耗时统计：成功/失败数、平均/最小/最大耗时、总耗时
- `asyncio.run()` 后恢复 `sys.stdout`，防止 redirect_stdout 竞争条件

### 改进 — xdev 默认并发数调整
- xdev 默认并发数从 4 调整为 16

### 修复 — Skill 文档中 80% 准确率歧义
- `extract_dev/SKILL.md` 和 `extract_workflow/SKILL.md` 中 "80%+ 准确率" 明确标注为正则方案可行性阈值，非整体目标准确率
- 强调整体目标以 Supervisor 指定的为准

## 2026-03-10

### 改进 — 事实提取 prompt 增加 MECE 原则
- 提取系统提示词新增 MECE 原则（相互独立，完全穷尽）：各事实之间不应重叠，覆盖片段中的所有事实性内容

### 新功能 — `extract_facts_from_text()` API
- 新增 `fact_extract.api.extract_facts_from_text()`：纯文本输入 → LLM 提取 → 事实列表（含内嵌 sources）
- 支持 `index_lines` 选项：按行索引为 evidence（默认）或整体单条
- 不依赖 plan/parts/merge 文件 IO，适合轻量级调用
- 返回格式：`{"facts": [...], "evidence_count": N, "fact_count": N}`

### 新功能 — evaluator.api `evaluate()` 统一接口
- 新增 `evaluate()` 函数，支持 object 和 list_of_objects 两种类型的批量评估
- 自动检测评估类型（看 `standard_list[0]` 是 list 还是 dict），也可通过 `eval_type` 强制指定
- re-export 核心类（`ObjectEvaluator`, `ListOfObjectsEvaluator`, `FullStandard`, `FullExtractedResult`, `Schema`, `EvaluationResult`）

### 修复 — evaluator.api 数据类型错误
- `compare()` 和 `evaluate_batch()` 内部使用了父类 `EvaluationStandard`/`EvaluationExtraction`，但评估器实际需要子类 `FullStandard`/`FullExtractedResult`
- 修改为使用 `FullStandard(id=..., labels=...)` 和 `FullExtractedResult.success_result(data=...)` 与内部调用链一致

### 文档 — evaluator_api_guide.md 重写
- 重写 evaluator API 使用指南，聚焦 evaluator 模块
- 新增 25 个测试用例覆盖 evaluate() 的 Object / ListOfObjects / 边界场景

## 2026-03-09

### 重构 — page → group 抽象统一
- **全局重命名**：pipeline 内部 `page` 概念统一为 `group`（仍为 int），支持 PDF 页码和非 PDF 分组（如章节）
- `EvidenceItem.page` → `EvidenceItem.group`，`PlanResult.total_pages` → `PlanResult.total_groups`
- CLI 参数：`--min-pages-per-task` → `--min-groups-per-task`，`--max-pages-per-task` → `--max-groups-per-task`
- Plan JSON：`total_pages` → `total_groups`，新增 `group_type`（`"page"` / `"txt_file"`）和 `group_labels` 字段
- Sections JSON：`done_pages` → `done_groups`，`failed_pages` → `failed_groups`
- Source JSON：`"page"` → `"group"`，新增 `"group_label"` 字段
- 不保留向后兼容

### 新功能 — 外部文本导入（`fact-extract import`）
- **`--source-type baojie`**：从 `NNN_标题.txt` 目录导入，自动生成 plan + sections
- 导入后 `group_type: "txt_file"`，1 group = 1 chapter，无需 docjson
- 提取阶段自动识别 `source_type: "txt_file"`，直接从 sections 构建 evidence（跳过 docjson）
- 新增 `importer.py`、`txt_sections_to_evidence_items()`、`extract_group_body_texts_from_sections()`

### 改进 — 合并阶段 source 命名与去重
- **source ID 格式**：从 `src_XXXX_N` 改为 `eNNNN`（如 `e0001`、`e0002`...），全局顺序编号
- **去重**：同一 task 内多条 fact 引用同一 evidence 时，只复制一份 source 文件
- 零补位宽度根据总 source 数自动计算（最少 2 位）

### 新功能 — Auto-Section（LLM 自动分段）
- **全书段落分段**：`--auto-section` 开启 LLM 逐页段落分段，替代 docjson 原始 section 节点作为 evidence 边界
- **断点续跑**：中间结果每 20 组持久化到 `facts/sections/<book_id>.json`，进程中断后自动从 `done_groups` 续跑
- **重试机制**：每组失败后自动重试（`--section-retries`，默认 2 次），重试耗尽后记录 `failed_groups` 并阻断 pipeline
- **宽容模式**：`--no-section-strict` 允许带失败组继续后续流程（失败组不影响其他组的分段结果）
- **独立子命令**：`fact-extract auto-section --plan ...` 可单独运行
- 默认并发 32 workers

### 新功能 — 提取反思校对
- **反思步骤**：LLM 提取后自动进行第二轮校对（逐 bundle 独立反思），检查遗漏、错误引用、拆分/合并不当
- 默认开启，`--no-reflect` 关闭
- 仅影响 `llm` / `llm-once` 后端（agentic 后端自有多轮对话能力）
- trace 记录 `fact_count_round1` / `fact_count_after_reflect` 便于对比

### 重构 — fact-extract evidence 格式升级
- **Evidence 段落粒度**：从句子级拆分改为段落级（一个 section 节点 = 一条 evidence），减少碎片化
- **表格 HTML 化**：表格从逐 cell 拆分改为整表合并，以 `<table>` HTML 格式作为单条 evidence
- **Evidence ID 简化**：从 `ev_0001` 改为 `e1`、`e2`...，配合 evidence registry 在后台维护页码/段落位置等元数据
- **Prompt 格式重写**：
  - System prompt：rules + output_schema 移入，固定不变
  - User prompt：纯文本格式 `[eN] 段落文本`，任务信息简化为一行
  - LLM 输出从 `page_refs` 改为 `evidence_refs`，由后处理查表还原分组
- **三后端统一**：llm / llm-once / agentic 共用同一套 evidence 生成 + prompt 格式
- **Agent 工具适配**：`WorkerFactInput.page_refs` → `evidence_refs`，`tool_worker_fact_add_batch` 从 registry 解析分组和源文本

### 重构 — agentic_extract 模块独立化
- **提取公共模块**：将 `model_factory.py`、`tools.py`、`hooks.py`、`retry.py` 从 `agentscope_agent` 提取到 `agentic_extract`，改用相对导入
- **解除 agentscope_agent 依赖**：`agentic_extract.agents` 和 `agentic_extract.labeling.agent` 不再依赖 `agentscope_agent`

### 新功能 — 文档 ID 白名单
- **`--std-ids` / `--std-ids-file`**：`xdev import-data` 和 `agentic-extract run` 新增参数，支持按文档 ID 过滤导入
  - `--std-ids`：逗号分隔的 ID
  - `--std-ids-file`：ID 文件（一行一个，支持 `#` 注释）
  - 白名单在 `ResourceGenerator` 层过滤，ID 归一化比较（兼容 UUID 格式差异）
  - 有白名单时自动跳过数据集缓存
- **白名单持久化**：`std_ids` 保存在 `manifest.json` 的 `DataSourceSetId.std_ids` 字段
- **`--sync`**：同步模式，导入后删除远程不存在的本地文档，保证本地数据与远程一致
- **`--skip-exist`**：跳过本地已有文档，不重新下载
- **从 manifest 读取参数**：`--sync` / `--skip-exist` 不指定 `--set-id` 时，自动从 manifest 读取上次的导入参数
- **当前入口文档**：[xdev_guide.md](./xdev_guide.md)

### 新功能 — 标注数据自动导入
- **`import_from_set_id` 增强**：从远程标准集导入时，自动从 `train.json` / `test.json` 提取标注数据到 `labels/` 目录

### 改进
- **允许无数据源运行**：`agentic-extract run` 不再强制要求指定数据源，支持使用已有 `.xdev` 数据

## 2026-03-06

### 新功能 — 增量添加文档与符号链接治理
- **`xdev import-data --add-pdf`**：增量添加 PDF 文档（单文件或目录），支持 `--force` 覆盖已有文档
- **`xdev import-data --reparse`**：重新解析已有 PDF 生成新 DocJSON，支持 `--doc-ids` 指定文档
- **`xdev fix-symlinks`**：检测和修复数据目录中的符号链接，`--fix` 替换为真实文件副本
- **`import-data` 自动检测**：执行导入操作前自动扫描并警告已有符号链接
- **历史能力**：`agentic-extract run --add-pdf` 曾支持工作流启动时增量添加 PDF；当前入口已迁移为 `xdev import-data --add-pdf`
- **符号链接治理**：`extract_dev/local_data.py` 移除 `symlink` 参数，始终使用真实文件复制
- **当前入口文档**：[xdev_guide.md](./xdev_guide.md)

### 新功能 — 标注状态检查
- **`xdev label-status`**：新增 CLI 命令，检查标注完整性与 schema 一致性
  - 摘要模式：显示文档总数、已标注/未标注/schema 不匹配数
  - `--detail` 模式：列出每个问题文档及具体问题（缺少字段、多余字段、类型错误）
- **Python API**：`check_label_status()` 返回 `LabelStatusReport`（含 `LabelIssue` 列表）
- **`label_all_documents` 增强**：新增 `relabel_mismatched` 参数，自动将 schema 不匹配文档加入重新标注队列
- **Business Skill 更新**：标注阶段补充检查步骤（标注前后运行 `label-status`，确保全量通过）
- **详细设计**：[features/label_status_check.md](./features/label_status_check.md)

## 2026-03-04

### 新功能 — fact-extract skill
- **新增 skill**：`agentic_extract/skills/fact-extract/SKILL.md`
  - 覆盖 PDF 事实抽取流程：`plan -> run --from extract -> merge`
  - 默认推荐 `llm-once` 并发模式，明确 `facts/` 目录结构与产物说明
  - 明确事实证据契约：模型返回页码索引，系统按页关联 source
- **`xdev export-skills` 导出清单更新**：新增 `fact-extract`，导出 ZIP 现包含：
  - `xdev`
  - `pdf_ai_explorer`
  - `extract_workflow`
  - `fact-extract`

## 2026-03-02 (续)

### 新功能 — 提取套件化
- **`xdev init`**：初始化 workspace 目录结构（git + 模板文件 + .xdev/），复用 extract_agent_common 模板
- **`xdev export-skills`**：导出所有 skills（xdev、pdf_ai_explorer、business、extract_dev）到 ZIP 文件，供 coding agent 加载
- **JSON 配置管理**：xdev 和 agentic-extract 支持三层配置
  - 全局配置：`~/.config/xdev/config.json` / `~/.config/agentic-extract/config.json`
  - 项目配置：`.xdev/config.json` / `.agentic-extract.json`
  - 优先级：CLI 参数 > 环境变量 > 项目配置 > 全局配置 > 默认值
- **集成测试**：`tests/integration/test_suite.py`（23 个测试，覆盖 init/import/list/doc/schema/label/run/eval/config/export-skills）

### 修复
- **`xdev/evaluation.py`**：`execute_on_docjson` / `batch_execute_on_docjsons` 为 async API，用 `asyncio.run()` 包装；修正字段名 `data` → `labels`；提取结果从包装格式中取 `data`
- **`xdev/import_data.py`**：修复引用已移除的 `XdevSettings`，改为 `load_config`
- **`xdev/config.py`**：从 pydantic-settings `BaseSettings` 重写为 `BaseModel` + JSON 配置文件加载
- **`xdev/cli.py` eval 命令**：修复 evaluator API 属性名（`accuracy` → `overall_accuracy`，`record_details` → `details`），修正 import 路径 `evaluation_models` → `models`

### 文档
- **`docs/agent_setup_guide.md`**：新增 Agent 环境配置指南（安装工具、安装 skills、配置、开始工作）
- **xdev SKILL.md**：新增"配套 Skills"章节（skill 速查表、工作流切换、各 skill 使用场景）；更新安装命令为 `uv tool install`

## 2026-03-02

### 修复
- **tiktoken 离线缓存**：预下载 `o200k_base.tiktoken` 编码文件到 `src/agentscope_agent/data/`，避免运行时因 SSL 连接失败（`openaipublic.blob.core.windows.net`）导致 Agent 崩溃
  - 文件名使用 URL 的 SHA1 hash（tiktoken 内部缓存格式）
  - `cli.py` 在导入前设置 `TIKTOKEN_CACHE_DIR` 环境变量指向内置数据目录
  - 文件随 wheel 打包分发，无需网络访问

### 新功能
- **批量评估脚本**：`scripts/eval_img_workspaces.sh` 并行执行所有 img workspace 的 `extract-dev train` 评估

## 2026-02-27

### 新功能
- **本地数据管道**：支持从本地 PDF 目录准备 workspace 并执行提取，无需远程数据集
  - `src/extract_dev/local_data.py`：本地数据管理模块（导入、manifest、空标注骨架生成）
  - `scripts/prepare_workspace.py`：一键准备 workspace（PDF→DocJSON + 数据导入 + schema 写入）
  - `scripts/prepare_docjson.py`：批量 PDF→DocJSON 转换脚本
  - `scripts/run_extract_to_excel.py`：从 workspace 执行提取并输出 Excel 报告
- **extract-dev 本地数据自动检测**：`cli.py`、`api.py`、`workflow.py` 优先使用 `.extract-dev/data/` 本地数据，fallback 到 set_id 远程下载

## 2026-02-26

### 新功能
- **pdf-ai-explorer 集成**：ExtractDevAgent、BusinessAgent、Supervisor 均可使用 pdf-ai-explorer 导航长文档
  - `extract-dev doc` 长文档（>10000字）自动截断，显示前 1000 字并提示 docjson 路径和 pdf-ai-explorer 命令
  - 新增 `extract-dev docjson-paths` 命令：批量获取条目ID→docjson路径
- **extract-dev workspace 支持**：CLI 全局 `--workspace` 选项 + 环境变量 `EXTRACT_WORKSPACE`
  - `resolve_path()` 统一路径解析，program 和 override 均相对于 workspace
  - API 层 `ExtractDevEvaluator.create(workspace=...)` 参数化传入
  - `override.py` 所有函数支持 `override_dir` 参数（API 显式传入，CLI 走全局 settings）

### 优化
- **extract-dev doc/standard 性能优化**：绕过 `_get_engine()` 全量加载，直接读索引文件 + 单文件
- **数据集下载优化**：先按 max_size 分割再下载资源，避免下载未使用的文件
- **无标注模式数据问题处理**：禁止记录 `data_issues.md`，要求直接通过 `ask_business_agent` 修正
- **API `_apply_override` 修复**：复用 `patch_engine_with_override` 统一处理 train/test，修复 API 评估结果不一致问题
- **pyproject.toml**：私有 index 加 `explicit = true`，避免不可达时阻塞构建

## 2026-02-25

### 新功能
- **ExtractDevAgent 上下文压缩**：上下文达到 90% 窗口容量时自动压缩
  - 使用 AgentScope `ReActAgent.CompressionConfig`，`OpenAITokenCounter(model_name="gpt-4o")` 估算 token
  - 新增配置：`ASA_MAX_CONTEXT_LENGTH`（默认 128000）、`ASA_COMPRESSION_KEEP_RECENT`（默认 10）
  - CLI 参数：`--max-context-length`、`--compression-keep-recent`
  - 仅 ExtractDevAgent 启用，其他 Agent 不受影响

## 2026-02-24

### 新功能
- **LabelingAgent 并发标注**：新增独立的标注 Agent，支持并发批量标注文档
  - 新增 `agents/labeling.py` - LabelingAgent 类，每次调用创建独立 ReActAgent 实例
  - 新增 `tools/labeling_workflow.py` - `create_label_all_documents_tool()` 工厂函数
  - 支持 16 并发（`asyncio.Semaphore`），自动区分 train/test 数据集
  - 支持指定 `doc_ids` 重试失败文档
  - 新增 `prompts/labeling.py` - LabelingAgent 提示词（含 `build_label_message()` 动态格式提示）
- **标注 Agent 独立模型配置**：支持为标注 Agent 配置独立的 LLM
  - CLI 参数：`--labeling-model`, `--labeling-api-base`, `--labeling-api-key`
  - 环境变量：`ASA_LABELING_MODEL`, `ASA_LABELING_API_BASE`, `ASA_LABELING_API_KEY`
  - 参数链路：CLI → config → workflow → Supervisor → BusinessAgent → labeling_workflow tool → LabelingAgent
- **list_of_objects Schema 类型支持**：BusinessAgent 和 LabelingAgent 提示词完整支持两种 schema 类型
  - `object`：单条记录，标注格式 `{"字段1": "值1"}`
  - `list_of_objects`：多条记录，标注格式 `[{"字段1": "值1"}, ...]`
  - `build_label_message()` 根据 schema type 动态生成格式提示

### 改进
- **ExtractDevAgent 初始化优化**：初始化步骤第 1 步改为检查并阅读 `business_guide.md`
- **LabelingAgent dataset 感知**：标注命令包含 `--dataset train/test` 参数，确保 train/test 数据集正确区分
- **BusinessAgent 无标注模式增强**：`UNLABELED_SYSTEM_PROMPT` 新增 Schema 类型说明、批量标注工具说明
- **run_extract_dev_agent 同步包装修复**：补全 `labeling_model/api_base/api_key` 参数传递

### 测试
- **LabelingAgent 单元测试**：新增 19 个测试用例（`tests/agentscope_agent/test_labeling.py`）
  - `TestLabelingPrompts`（7 个）：SYSTEM_PROMPT 内容、build_label_message 各参数注入、格式提示
  - `TestLabelingAgent`（3 个）：配置存储、成功/失败返回、独立 Agent 实例
  - `TestLabelAllDocumentsTool`（9 个）：工具创建、无 schema 错误、全量成功、部分失败、指定 doc_ids、兜底指导文本

## 2026-02-10

### 新功能
- **提取策略增强**：重写策略提示词，新增 3 个策略（结构定位+llm_select、表格结构化提取、分字段组合），移除 NER 引用
  - 策略 2：结构定位 + llm_select 缩小范围 → extract 提取（章节粗筛、段落精筛、句子级精选）
  - 策略 3：表格结构化提取（LLM 分析表头映射，代码遍历提取）
  - 策略 4：分字段组合（不同字段特征选不同方法）
  - 文件：`src/agentscope_agent/prompts/strategies.py`
  - 文档：`docs/features/extraction_strategies.md`
- **Document 模型增强**：新增便利方法支持策略代码
  - `TableNode`：`cell_at()`, `row()`, `col()`, `iter_rows()`, `to_text()` — 表格行列访问和文本格式化
  - `Node`：`collect_content()` — 递归收集后代内容（文本 + TableNode）
  - `Document`：`get_all_texts()` — 全文段落文本 flat list
  - 文件：`src/code_executor/document/models/nodes.py`, `src/code_executor/document/models/document.py`
- **extract-dev context 文档更新**：`get_llm_context()` 输出补充新增 API
  - Document: `get_all_texts()`、Node: `collect_content()`、TableNode: `cell_at()`/`row()`/`col()`/`iter_rows()`/`to_text()`
  - 示例代码更新为使用新 API 的模式
  - 文件：`src/code_executor/utils.py`

### 测试
- **Document 模型单元测试**：新增 40 个测试用例
  - 测试数据：`resources/SINGLE_FILES/91cb4734-.../doc.json`（易点天下 2024 年报）
  - 覆盖：Document 加载/查询、Node 导航、collect_content、TableNode 行列访问（含合并单元格）
  - 文件：`tests/code_executor/test_document_model.py`

## 2026-02-04

### 修复
- **Schema 类型推断支持 int/float 共存**：修复标准集字段同时包含整数和浮点数时报错的问题
  - 问题：`_infer_field_type()` 对同一字段出现 int 和 float 两种类型时抛出 `字段有多种非str类型` 错误
  - 方案：int 和 float 共存时统一推断为 `float`（float 是 int 的超集）
  - 兼容现有 schema 和缓存，不引入新类型
  - 文件：`src/evaluator/standards/dataset_app.py`

## 2026-02-03

### 修复
- **ContextVar 跨上下文 Policy 丢失**：修复 `create_default_tool_hub()` 在 FastAPI 请求等新异步上下文中返回空 ToolHub 的问题
  - 问题：`ContextVar` 的值在不同异步上下文中是隔离的，模块导入时设置的 Policy 在新 Context 中不可见
  - 方案：`get_global_policy()` 在当前 Context 没有 Policy 时自动从环境变量重新加载配置
  - 文件：`src/code_executor/tools/tool_center.py`

## 2026-01-31 (状态恢复 tool_use 清理)

### 修复
- **状态恢复时清理未完成的 tool_use 消息**：解决中断后恢复状态时 API 报错的问题
  - 问题：当程序在 tool_use 消息发送后、tool_result 返回前中断时，恢复后 memory 最后一条消息是 tool_use，API 不接受这种消息历史
  - 方案：在 `SessionManager.load_agent_state()` 和 `load_supervisor_state()` 后自动检测并删除尾部连续的 tool_use 消息
  - 使用 AgentScope 官方 API：`msg.has_content_blocks("tool_use")` 检测，`memory.delete()` 删除
  - 删除时打印日志：`[extract-dev-agent] 清理了 N 条未完成的 tool_use 消息`

## 2026-01-31 (Supervisor 解析模式)

### 新功能
- **Supervisor 响应解析模式**：新增 `ParseMode` 枚举，支持两种解析方式
  - `ParseMode.TEXT_LINE`（默认）：从最后一行往前扫描，匹配 `[DONE]`/`[CONTINUE]`/`[BUSINESS]`
  - `ParseMode.STRUCTURED_OUTPUT`：使用 AgentScope structured output 功能，通过 Pydantic model 获取结构化决策
  - 新增 `SupervisorDecision` Pydantic model
  - 文本模式未匹配到决策标记时记录 warning 日志

## 2026-01-31 (策略更新)

### 重构
- **策略提示词重写**：从「LLM 优先」改为「选择最合适的方法（正则 vs LLM）」
  - 新增决策流程：快速试探 → 正则验证 → 评估反馈 → 切换判断
  - 新增正则适用判断标准：初版高准确率、每次优化 10%+、最终 80%+
  - 新增快速试探示例（grep -P/grep -E/Python 兼容 Linux/macOS）
- **Supervisor 策略感知**：Supervisor 现在也包含策略信息，给建议时可参考这些原则

## 2026-02-01

### 重构
- **workspace 模板迁移到包内**：解决包安装后无法找到模板的问题
  - 模板从 `resources/templates/workspace_setup/` 迁移到 `src/extract_agent_common/templates/`
  - 使用 `importlib.resources` 访问包内资源，支持开发模式和安装后使用
  - 模板文件会自动包含在 wheel 中

### 修复
- **pyproject.toml 缺失包导出**：添加 `extract_agent_common` 到 hatch packages 列表

### 重构
- **code_executor 统一接口**：重构 `execute()` 为统一入口函数，支持所有参数组合
  - 输入源（互斥）：`program`（代码字符串）/ `program_path`（文件路径）/ `workspace`（目录路径）
  - 数据格式（互斥）：`data`（已转换数据）/ `docjson`（原始 DocJSON）
  - 输出模式：`capture_output=True` 返回 `(result, stdout, stderr)` 元组
  - PDF 支持：`pdf_bytes` 参数传递原始 PDF 数据
  - 使用 `@overload` 提供精确的类型提示
- **废弃旧接口**：以下函数标记为 `@deprecated`，触发 `DeprecationWarning`：
  - `execute_from_file`, `execute_from_workspace`
  - `execute_from_file_on_docjson`, `execute_from_workspace_on_docjson`
  - `execute_with_output`, `do_extract`, `do_extract_with_output`
- **迁移所有模块**：`evaluation_engine`, `code_executor/api.py`, `extract_dev/api.py` 统一使用新接口

### 修复
- **batch_execute 参数错误**：修复使用位置参数导致的调用失败

## 2026-01-31

### 新功能
- **extract-dev Code API**：新增面向对象的异步 Python API
  - `ExtractDevEvaluator` 评估器类：支持 `evaluate_train()`, `evaluate_test()`, `run_extract()` 异步方法
  - `extract_from_docjson()` 独立提取函数，不依赖评估器
  - 三种输入方式互斥：`program`（代码字符串）/ `workspace`（目录路径）/ `config`（配置字典）
  - `EvaluationResultWithMetadata` 带元数据的评估结果，支持 `result.save()` / `.load()` 保存加载
  - 元数据在创建评估器时记录：`set_id`, `base_url`, `cache_dir`（远程）或 `data_path`（本地）
  - `SafeJSONEncoder` 安全 JSON 编码器，支持 Ellipsis (`...`), set, bytes, inf, nan 等特殊值
- **code_executor API 重构**：
  - `execute_on_docjson(docjson, program/workspace/config, pdf_bytes)` 支持三种输入方式
  - 所有 docjson 相关函数支持 `pdf_bytes` 参数
  - `execute_workspace_on_docjson` 标记为废弃
  - 文档：更新 `docs/extract_dev_guide.md`
- **extract-dev 进度打印**：train/test 命令现在显示实时执行进度
  - 显示每个文档的处理状态：`doc_id 处理中...` → `[n/total] doc_id ✓/✗ (Xs)`
  - 按完成顺序显示（并发执行，数字可能乱序）
  - 显示整体统计：`完成: n/total 成功, 总耗时 Xs`
- **extract-dev run 耗时显示**：run 命令现在显示执行耗时
- **ProgressCallback 类型**：`evaluation_engine` 新增进度回调类型导出
  - `ProgressCallback`, `ProgressEvent`, `ProgressStart`, `ProgressDone`
  - `evaluate_program()` 新增 `progress_callback` 参数

### 修复
- **修复进度打印被 redirect_stdout 捕获的问题**（临时修复）
  - 问题：`redirect_stdout` 在多线程环境存在竞争条件，导致主线程 print 被捕获
  - 临时方案：进度回调使用 `sys.__stdout__` 绕过重定向，`asyncio.run()` 后恢复 stdout
  - 正式修复方案：待实现 ThreadLocal 方案，详见 [redirect_stdout_thread_safety.md](./features/redirect_stdout_thread_safety.md)

## 2026-01-30

### 新功能
- **evaluation_engine 配置模块**：新增 pydantic-settings 配置支持
  - 新增 `evaluation_engine/settings.py` - Settings 配置类
  - 配置文件：`.evaluation_engine.env`
  - 环境变量前缀：`EVALENG_`
  - 支持 `EVALENG_PROG_RUN_CONCURRENT` 配置程序执行并发数（默认 4）
- **extract-dev 并发参数**：train/test 命令新增 `--concurrent` 参数
  - 优先级：CLI 参数 > 环境变量 > 配置文件 > 默认值
- **extract-dev 默认下载 PDF**：extract-dev 现在默认下载 PDF 文件，支持 VLMExtractTool
- **extract-dev 报错样例输出**：train/test 评估报告现在会显示提取报错的文档 ID（最多 10 个）
- **do_extract_with_output**：新增捕获 stdout/stderr 的执行函数
  - 在线程内部捕获输出，避免并发安全问题
  - 返回 `(result, stdout, stderr)` 元组

### 修复
- **修复 extract-dev train/test 输出为空的问题**
  - 根本原因：`redirect_stdout/stderr` 在并发环境下不是线程安全的
  - 解决方案：把 redirect 移到 `asyncio.to_thread` 的线程内部执行
- **修复 evaluate_program 并发模式**：coroutine 现在在 `extract_with_semaphore` 内部创建
- **添加 train/test 命令异常处理**：捕获并显示错误信息

### 重构
- **环境变量加载重构**：`extract_agent_common/workspace.py`
  - 新增 `_load_env_file()` 通用函数
  - 新增 `_load_evaluation_engine_env()` 加载评估引擎配置
  - `setup_environment()` 现在同时加载 `.code_tools.env` 和 `.evaluation_engine.env`
- **删除重复代码**：删除 `agentscope_agent/workflow.py` 中重复的 `_load_code_tools_env` 函数
- **ExtractDevAgent 提示词重构**：强化策略提示词的强制性
  - `strategies.py` 策略内容改为强制性语气
  - 策略位置移至“初始化步骤”之后，新增“强制策略（必须遵守）”声明
  - 示例代码从 `article: list` 改为 `document: Document`，保持中性
  - 移除暗示正则处理的提示语

### 新功能
- **PDFToImageTool**：新增 PDF 转图片工具，配合 VLMExtractTool 使用
  - 支持从 PDF bytes 转换指定页面为 PNG 图片
  - 可配置 DPI（默认 150）
  - 依赖 `pymupdf>=1.24.0`
- **PDF 数据流**：支持在提取函数中访问原始 PDF 数据
  - `code_executor.Document` 新增 `raw_bytes` 属性
  - `evaluator.Document` 新增 `pdf_path` 和 `get_pdf_bytes()` 方法
  - `ResourceGenerator.download_resources()` 新增 `download_pdf` 参数
  - `code_executor.create_input()` 新增 `pdf_bytes` 参数

### 重构
- **策略提示词迁移**：`src/code_executor/tools/prompts/` 迁移到 `src/agentscope_agent/prompts/strategies.py`
  - 新增 `STRATEGIES` 常量提供工具使用策略指导

### 修复
- **extract-dev context 工具显示**：修复 workspace 目录下运行 `extract-dev context` 时代码工具不显示的问题
  - 在 `setup_environment()` 之前加载项目根目录的 `.code_tools.env` 到环境变量

### 文档
- 重构 VLM 相关文档，拆分为 5 个独立文档：
  - `vlm_extract_solution.md` - VLM 提取方案入口文档
  - `vlm_tools.md` - VLM 工具 API
  - `pdf_data_flow.md` - PDF 数据流
  - `tool_strategies.md` - 策略提示词设计
  - `code_tools_context.md` - 代码工具上下文机制
- 删除旧文件 `vlm_extract_tool.md`

## 2026-01-29

### 新功能
- **VLMExtractTool**：新增 VLM 图片信息提取工具
  - 支持多种输入格式：URL、base64、本地文件路径、bytes
  - 支持单图和多图（多图一起分析提取一份结构化数据）
  - 通过 pydantic schema 定义输出结构
  - magic number 自动检测图片 MIME 类型
  - 可配置的图片大小限制（默认 20MB）
  - 文档：[features/vlm_extract_tool.md](./features/vlm_extract_tool.md)
- **添加 diskcache 依赖**：修复 `code_executor.document.cache` 模块的缺失依赖

### 变更
- **移除 openhands_agent 模块**：删除 `src/openhands_agent/` 目录及相关依赖（openhands-sdk、openhands-tools）
- **agentscope-agent CLI 入口**：新增 `agentscope-agent` 命令到 pyproject.toml scripts
  - 使用方式：`uv run agentscope-agent run ...`（替代原来的 `python -m agentscope_agent`）

### 新功能
- **code_executor Workspace 执行**：支持从 workspace 目录加载并执行 `program.py`
  - 新增 `execute_from_workspace(workspace, data)` - 从 workspace 执行
  - 新增 `execute_from_workspace_on_docjson(workspace, docjson)` - 自动检测输入模式
  - 新增 `execute_from_file(program_path, data)` - 从文件路径执行
  - 新增 `execute_from_file_on_docjson(program_path, docjson)` - 自动检测输入模式
  - 新增 `batch_execute_workspace_on_docjsons()` - 批量执行
- **自动检测输入模式**：根据 `extract()` 函数签名自动选择 tree/flat 模式
  - 新增 `detect_input_mode(func)` - 检测函数签名推断输入模式
  - 检测规则：类型注解 > 参数名 > 环境变量
  - `def extract(doc: Document)` → tree 模式
  - `def extract(article: list)` → flat 模式
  - `create_input(docjson, mode)` 支持显式指定模式

### 文档
- 更新 `docs/code_executor_usage.md`：添加 Workspace 执行和自动检测输入模式说明
- 更新 `docs/system-design.md`：更新 code_executor 模块 API 列表

## 2026-01-28

### 新功能
- **agentscope_agent `--set-id` 参数**：支持通过命令行指定标准集 ID
  - CLI 参数：`--set-id`
  - 环境变量：`ASA_SET_ID`
  - 运行时自动设置 `EXTRACT_SET_ID` 环境变量
- **工作区自动提交**：Agent 运行结束时自动提交工作区变更
  - 正常退出和异常退出（包括 Ctrl+C）都会触发提交
  - 无变更时记录日志并跳过
  - 新增 `commit_workspace()` 函数
- **代码质量工具集成**：集成 ruff、tree-sitter、mypy、pytest 等工具提升 Agent 编码能力
  - 新增 `hooks/ruff_check.py` - 基于 post_acting hook 的自动代码检查
  - 新增 `tree-sitter-cli` 命令行工具（`src/tree_sitter_cli.py`）
  - 新增 `prompts/tools/` 目录：ruff.py、tree_sitter.py、mypy.py、pytest_cov.py
  - 文档：`docs/features/code_quality_tools.md`
- **BusinessAgent 业务分析 Agent**：新增可选的业务分析 Agent，用于提供标准集业务解释和指导
  - CLI 参数：`--enable-business-agent`、`--business-agent-model`
  - 环境变量：`ASA_ENABLE_BUSINESS_AGENT`、`ASA_BUSINESS_AGENT_MODEL`
  - 新增 `prompts/business.py` - BusinessAgent 系统提示词
  - 新增 `agents/business.py` - BusinessAgent 类
  - 新增 `tools/business_agent_tool.py` - `ask_business_agent` 工具
  - 启用时自动生成 `business_guide.md` 业务指导文档

### 重构
- **Supervisor 统一**：将原有的 `SupervisorAgent` 和 `CoordinatorSupervisor` 合并为统一的 `Supervisor` 类
  - `Supervisor` 通过 `enable_business_agent` 参数控制是否启用 BusinessAgent
  - 合并 `run_with_business_agent_async` 到 `run_agent_async`，通过参数区分模式
  - 简化 CLI 调用逻辑
- **标准集 ID 统一**：
  - `extract-dev run` 命令的 `doc_id` 参数重命名为 `standard_entry_id`
  - `extract-dev` 的 `--doc-ids` 参数重命名为 `--standard-entry-ids`，明确语义
  - 标准集本地存储新增 `document_id` 字段，区分标准集条目 ID 和原始文档 ID
  - 删除废弃的 `url_loader.py` 和 `EvaluationEngine.from_url()` 方法

### 文档
- 新增 `docs/standard_set_local_storage.md`：标准集本地存储格式说明
- 更新多个文档中的 `--doc-ids` 为 `--standard-entry-ids`

### 新功能
- **文件写入行数限制**：新增可选的文件写入行数限制模式，用于减少 LLM 单次输出的 token 量
  - CLI 参数：`--limit-write-lines`、`--max-write-lines`
  - 环境变量：`ASA_LIMIT_WRITE_LINES`、`ASA_MAX_WRITE_LINES`
  - 新增 `tools/` 子模块：`register_file_tools()`、`create_limited_file_tools()`
  - 所有 Agent（ExtractDevAgent、SupervisorAgent、CodeAgent）均支持此功能
- **insert_text_file 工具**：所有 Agent 现在默认注册 `insert_text_file` 工具

### 重构
- 新增 `agentscope_agent/tools/` 模块，统一管理文件写入工具注册逻辑

### 文档
- 更新 `docs/agentscope_agent_design.md`：添加文件写入限制功能说明
- 更新 `docs/project-rules.md`：添加 tools/ 模块和新参数

## 2026-01-27

### 新功能
- **CodeAgent 子代理**：新增可选的 CodeAgent 子代理，用于处理具体的代码优化任务
  - CLI 参数：`--enable-code-agent`、`--code-agent-model`
  - 环境变量：`ASA_ENABLE_CODE_AGENT`、`ASA_CODE_AGENT_MODEL`
  - 新增 `prompts/code_agent.py` - CodeAgent 系统提示词
  - 新增 `agents/code_agent.py` - `create_code_agent_tool()` 函数
- **--standard-entry-ids 参数**：`extract-dev` 的 train/test 命令支持 `--standard-entry-ids` 参数，用于筛选指定标准集条目进行评估
  - 新增 `evaluation_engine.EvaluationEngine.evaluate_program()` 的 `std_ids` 参数
  - 新增 `evaluation_engine.api.evaluate_program()` 的 `std_ids` 参数

### 重构
- `agentscope_agent/prompts.py` 拆分为 `prompts/` 目录：
  - `prompts/extract_dev.py` - ExtractDevAgent 提示词
  - `prompts/supervisor.py` - SupervisorAgent 提示词
  - `prompts/code_agent.py` - CodeAgent 提示词
- `agentscope_agent/` 模块重构，按职责拆分为多个子模块：
  - `tracking/` - 监控统计（TokenStats, TokenTrackingModelWrapper）
  - `state/` - 状态管理（StateSaver, SessionManager）
  - `agents/` - Agent 实现（ExtractDevAgent 工厂, SupervisorAgent）
  - `workflow.py` - 主流程编排

### 文档
- 更新 `docs/agentscope_agent_design.md`：添加 CodeAgent 和 prompts/ 目录说明
- 新增 `docs/features/code_agent_feature.md`：CodeAgent 实现计划文档

## 2026-01-26

### 文档更新
- 更新 `docs/project-rules.md`：补充模块依赖关系、完善 API 列表
- 更新 `docs/system-design.md`：添加各模块的主要 API 说明和详细文档链接
- 创建 `docs/CHANGELOG.md`：记录主要修改
- 更新 `docs/simple_workflow_usage.md`：添加新参数（user_instruction, enable_tools, enabled_tools, max_iteration 等）
- 更新 `docs/extract_dev_guide.md`：train/test 命令新增参数（--key, --show-correct-ids, --show-incorrect-ids, --show-details）
- 更新 `docs/extract_dev_design.md`：CLI 设计部分反映新参数
- 创建 `docs/code_executor_usage.md`：code_executor 模块详细使用文档
- 创建 `docs/evaluator_usage.md`：evaluator 模块详细使用文档
- 创建 `docs/evaluation_engine_usage.md`：evaluation_engine 模块详细使用文档

## 2026-01-23

### 新增模块
- `agentscope_agent/` - AgentScope Agent 实现
- ~~`openhands_agent/` - OpenHands Agent 实现~~（已于 2026-01-29 移除）

### 文档
- 新增 `agentscope_agent_design.md`

## 2026-01-21

### 新增模块
- `extract_agent_common/` - Agent 公共模块，提供 workspace 管理功能
  - `create_workspace()` - 创建或复用工作目录
  - `setup_environment()` - 设置环境变量

## 2026-01-20

### 新增模块
- `llm_standard_generator/` - LLM 标准生成器
  - `generate_standards()` - 批量生成标准集数据
  - `DocumentInput`, `StandardResult` - 数据类

### 文档
- 新增 `extract_dev_guide.md`
- 新增 `extract_dev_design.md`

## 2026-01-09

### 重构
- `evaluator/` 模块重构
  - 拆分 `core/`, `evaluators/`, `standards/` 子模块
  - 新增 `ObjectEvaluator`, `ListOfObjectsEvaluator`
  - 新增 `StandardSet`, `StandardSetManager`, `DatasetEvaluator`

### 文档
- 新增 `evaluator-refactor-plan.md`

## 2026-01-08

### 重构
- 模块化重构完成
  - `simple_workflow/` - 核心工作流
  - `evaluation_engine/` - 评估引擎
  - `code_executor/` - 代码执行器
  - `evaluator/` - 评估器
  - `extract_dev/` - AI Agent 开发工具
  - `langchain_llm/` - LLM 客户端
  - `memect_apiserver/` - API 服务

### 兼容性
- 创建 `extract_agent/` 兼容模块，旧路径会触发 DeprecationWarning

### 文档
- 新增 `refactor_plan_archived.md`
- 新增 `simple_workflow_usage.md`
- 新增 `simple_workflow_返回格式标准.md`
