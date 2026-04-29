# agentic-extract Workspace / Runtime 文件整理方案、执行计划与完成记录

## 0. 执行结果

本方案已执行完成。

完成日期：

- 2026-04-16

阶段测试结果：

- 阶段一：`uv run pytest tests/agentic_extract/test_workspace.py tests/integration/test_suite.py -q`
  - 结果：`30 passed`
- 阶段二：`uv run pytest tests/agentic_extract/test_state.py tests/agentic_extract/test_runner.py tests/agentic_extract/test_cli.py -q`
  - 结果：`14 passed`
- 阶段三：`uv run pytest tests/agentic_extract/test_prompts.py tests/agentic_extract/test_cli.py tests/agentic_extract/test_api.py tests/agentscope_agent/test_labeling.py -q`
  - 结果：`35 passed`
- 最终回归：`uv run pytest tests/agentic_extract tests/agentscope_agent/test_labeling.py tests/integration/test_suite.py -q`
  - 结果：`108 passed`

最终状态：

- workspace 初始化不再默认生成冗余 `docs/*.md` 与 `logs/*.md` 文件。
- runtime 状态文件已迁移到 `.agent_state/`，并兼容读取旧版 `logs/...`。
- prompt / skills / guide / tests 已与新的 workspace/runtime 语义对齐。

## 1. 已确认决策

- 保留 `business_guide.md`。
- 保留 `.agent_state/*.json`。
- 将 `logs/current.json` 迁移到 `.agent_state/current.json`。
- 将 `logs/iterations/iter_NNN.json` 迁移到 `.agent_state/iterations/iter_NNN.json`。
- 第一阶段先删除“默认创建但不影响运行机制”的文件。
- 第二阶段做 runtime 状态文件迁移。
- 第三阶段再清 prompt / skills / docs / tests 里的旧引用。
- workspace 状态只暴露业务/数据事实，不把 agent 运行态混进 workspace 状态。

## 2. 目标与非目标

### 2.1 目标

- 明确区分“workspace 对外可见资产”和“agent runtime 内部状态”。
- 去掉默认生成但不是运行机制必需的噪音文件。
- 让 runtime 状态文件全部收敛到 `.agent_state/`。
- 保持现有运行机制可用，并对已有 workspace 提供迁移兼容。
- 每个阶段都有明确测试点，阶段测试通过后再进入下一阶段。

### 2.2 非目标

- 本次不删除 `business_guide.md`。
- 本次不删除 `.agent_state/*.json`。
- 本次不重新设计 workspace 生命周期模型。
- 本次不把 agent 运行态塞进 workspace 状态接口。
- 本次不要求在迁移阶段自动删除旧路径下已存在的 `logs/current.json` 或 `logs/iterations/iter_NNN.json`。

## 3. 目标目录语义

### 3.1 对外可见的 workspace 资产

- `program.py`
- `business_guide.md`（可选，但保留明确语义）
- `tests/`
- `.xdev/schema.json`
- `.xdev/data/...`
- `.xdev/labels/...`

### 3.2 agent runtime 内部状态

- `.agent_state/current.json`
- `.agent_state/iterations/iter_NNN.json`
- `.agent_state/*.json`（agent memory 等内部状态）

### 3.3 不再作为默认产物的文件

- `logs/agent_history.md`
- `logs/supervisor_history.md`
- `logs/plan.md`
- `logs/supervisor_plan.md`
- `docs/data_issues.md`
- `docs/known_limitations.md`
- `docs/notes.md`

## 4. 总体执行顺序

1. 阶段一：删除默认创建的冗余文件。
2. 阶段二：迁移 runtime 状态文件到 `.agent_state/`。
3. 阶段三：清理 prompt / skills / docs / tests 里的旧引用。
4. 阶段三完成后做一次全量回归。

执行原则：

- 每一阶段结束后必须先跑该阶段测试。
- 阶段测试未通过，不进入下一阶段。
- 兼容性改动优先于“彻底清理”。

## 5. 阶段一：删除默认创建的冗余文件

### 5.1 目标

删除初始化逻辑中默认创建的噪音文件，但不改变 runtime 机制，不迁移状态文件路径。

### 5.2 范围

本阶段只处理以下默认创建文件：

- `logs/agent_history.md`
- `logs/supervisor_history.md`
- `logs/plan.md`
- `logs/supervisor_plan.md`
- `docs/data_issues.md`
- `docs/known_limitations.md`
- `docs/notes.md`

本阶段不处理：

- `business_guide.md`
- `logs/current.json`
- `logs/iterations/iter_NNN.json`
- `.agent_state/*.json`

### 5.3 主要改动点

- 停止在 `src/extract_agent_common/workspace.py` 默认创建以上 7 个文件。
- 停止在 `src/xdev/workspace.py` 默认创建以上 3 个 `docs/*.md` 文件。
- 不在本阶段改动 prompt、skills、runtime 路径。
- 保持 `xdev init` / workspace init 的核心布局可用。

### 5.4 执行清单

- [x] 清理 `src/extract_agent_common/workspace.py` 中的默认文件创建逻辑。
- [x] 清理 `src/xdev/workspace.py` 中的默认文件创建逻辑。
- [x] 审查是否仍需保留空目录创建；如不影响机制，可保持最小改动，仅删除文件创建。
- [x] 更新相关测试，移除“这些文件必须存在”的断言。
- [x] 新增或更新测试，明确断言“初始化后这些文件默认不存在”。

### 5.5 阶段测试

自动化测试：

- `uv run pytest tests/agentic_extract/test_workspace.py tests/integration/test_suite.py -q`

建议补充的断言：

- `init_workspace()` 之后，核心文件仍存在：
  - `.gitignore`
  - `program.py`
  - `tests/conftest.py`
  - `tests/test_extract.py`
  - `.xdev/`
- 上述 7 个冗余文件默认不存在。

手工验收：

- 新建一个临时 workspace，执行一次 `xdev init`。
- 确认 workspace 可以正常初始化。
- 确认以上 7 个文件没有被默认生成。

阶段通过标准：

- 阶段一自动化测试通过。
- `xdev init` 基本可用，没有因为默认文件删除而破坏初始化流程。

## 6. 阶段二：迁移 runtime 状态文件到 `.agent_state/`

### 6.1 目标

将 runtime bookkeeping 从 `logs/` 迁入 `.agent_state/`，明确其“内部运行状态”语义，同时兼容已有 workspace。

### 6.2 目标路径

- `logs/current.json` -> `.agent_state/current.json`
- `logs/iterations/iter_NNN.json` -> `.agent_state/iterations/iter_NNN.json`

### 6.3 兼容策略

- 读取时：优先读取新路径；新路径不存在时兼容读取旧路径。
- 写入时：统一写入新路径。
- 本阶段不自动删除旧路径下的历史文件。
- 旧 workspace 在不做人工迁移的情况下，仍应能继续运行并延续迭代编号与 recent summary。

### 6.4 主要改动点

- 调整 `src/agentic_extract/state.py` 中 runtime 文件路径。
- 兼容旧路径下的 `current.json` 与 `iter_NNN.json` 读取。
- 调整 `scripts/agentic_batch.sh` 的状态读取逻辑。
- 更新测试中的路径断言。
- 保持 `business_guide.md` 与 `.agent_state/*.json` 的现有语义不变。

### 6.5 执行清单

- [x] 在 `StateManager` 中定义新的 runtime 路径。
- [x] 为 `current.json` 增加“新路径优先、旧路径兜底”的读取逻辑。
- [x] 为 `iter_NNN.json` 增加“新路径优先、旧路径兜底”的读取逻辑。
- [x] 写入逻辑改为统一写新路径。
- [x] recent summary、迭代编号延续、完成/失败状态更新在迁移后保持可用。
- [x] 更新 `scripts/agentic_batch.sh` 读取状态文件的路径逻辑。
- [x] 更新单元测试与兼容性测试。

### 6.6 阶段测试

自动化测试：

- `uv run pytest tests/agentic_extract/test_state.py tests/agentic_extract/test_runner.py tests/agentic_extract/test_cli.py -q`

建议补充的测试点：

- 新 run 会把 `current.json` 写到 `.agent_state/current.json`。
- 新 run 会把 `iter_001.json` 写到 `.agent_state/iterations/iter_001.json`。
- 旧 workspace 只有 `logs/current.json` 时，仍能正确读取迭代号与状态。
- 旧 workspace 只有 `logs/iterations/iter_NNN.json` 时，`get_recent_summary()` 仍可工作。
- 迁移后不会覆盖历史迭代记录。

手工验收：

- 选一个已有 workspace，保留旧的 `logs/current.json` / `logs/iterations/...`。
- 执行一次 agentic-extract 运行。
- 确认新的 runtime 文件写入 `.agent_state/`。
- 确认最近迭代摘要、状态判断和迭代号续接正常。

阶段通过标准：

- 阶段二自动化测试通过。
- 兼容旧 workspace 的 smoke test 通过。
- `scripts/agentic_batch.sh` 能继续判断运行状态。

## 7. 阶段三：清理 prompt / skills / docs / tests 里的旧引用

### 7.1 目标

清除“旧文件约定”对 agent 行为和文档描述的污染，使代码、prompt、skills、文档、测试与新的 workspace/runtime 语义保持一致。

### 7.2 主要清理对象

代码与 prompt：

- `src/agentic_extract/prompts/extract_dev.py`

skills：

- `src/agentic_extract/skills/extract_dev/SKILL.md`
- `src/agentic_extract/skills/extract_workflow/SKILL.md`
- `src/agentic_extract/skills/xdev/SKILL.md`

文档：

- `docs/agentic_extract_guide.md`
- `docs/xdev_guide.md`
- 以及所有仍把 `logs/plan.md`、`docs/data_issues.md`、`docs/known_limitations.md`、`docs/notes.md` 描述为默认产物或推荐工作流的文档

测试：

- 所有仍然断言旧文件存在，或仍基于旧 prompt 文本约定的测试

### 7.3 清理原则

- 保留 `business_guide.md` 的语义。
- 不再要求 DevAgent 把计划写入 `logs/plan.md`。
- 不再把 `docs/*.md` 当作默认工作产物。
- 文档中如果仍需要提到这些文件，必须改成“可选人工记录文件”，而不是默认生成或流程必需文件。

### 7.4 执行清单

- [x] 清理 `extract_dev` prompt 中对 `logs/plan.md` 的要求。
- [x] 清理 prompt / skills 中对 `docs/data_issues.md`、`docs/known_limitations.md`、`docs/notes.md` 的默认引用。
- [x] 更新 guide / design / workflow 文档中的 workspace 目录说明。
- [x] 盘点并删除明显失效、仅描述旧默认文件布局的文档内容。
- [x] 为 prompt / 文档清理补充测试或文本断言。
- [x] 复核 CLI / API 文档，使其与迁移后的路径和工作流一致。

### 7.5 阶段测试

自动化测试：

- `uv run pytest tests/agentic_extract/test_cli.py tests/agentic_extract/test_api.py tests/agentscope_agent/test_labeling.py -q`

建议新增测试：

- prompt 文本测试：断言 `extract_dev` prompt 不再要求写 `logs/plan.md`。
- prompt 文本测试：断言不再把 `docs/*.md` 描述为默认工作产物。
- workspace 文本/状态测试：保留 `business_guide.md` 的相关行为。

手工验收：

- 导出或查看最终 prompt，确认没有旧路径硬编码。
- 抽查更新后的 guide / design 文档，确认 workspace 结构描述一致。
- 使用 CLI 和高层 Python API 各做一次 smoke 检查，确认说明与实际行为一致。

阶段通过标准：

- 阶段三自动化测试通过。
- prompt / skills / docs 中不再把旧文件当作默认机制的一部分。
- CLI / API / workspace 文档表达统一。

## 8. 最终回归

阶段三完成后，执行一次最终回归。

自动化回归：

- `uv run pytest tests/agentic_extract tests/agentscope_agent/test_labeling.py tests/integration/test_suite.py -q`

建议 smoke：

- CLI smoke：选一个可运行 workspace，执行一次 `agentic-extract run` 或 `agentic-extract auto`。
- Python API smoke：执行一次高层 API 调用，确认 callback、heartbeat、状态文件路径与文档一致。

最终通过标准：

- 全量测试通过。
- 新建 workspace 不再默认生成冗余文件。
- runtime 状态已迁入 `.agent_state/`。
- 旧 workspace 兼容运行。
- prompt / skills / docs / tests 与新约定一致。

## 9. 实施时的注意事项

- 阶段一不要混入 runtime 路径迁移，避免问题定位困难。
- 阶段二优先保证兼容读，避免旧 workspace 直接失效。
- 阶段三再做“语言层面的清理”，避免代码已改但 prompt / docs 仍说旧话。
- 每一阶段完成后都先测试、确认，再继续下一阶段。
