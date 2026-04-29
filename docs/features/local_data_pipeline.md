# 本地数据管道：从 PDF 到 Agent 迭代

本文档描述如何使用本地 PDF 文件准备 workspace，并通过 agentscope-agent 进行无标注模式的提取迭代。

## 概览

```
PDF 文件 → DocJSON → workspace 数据导入 → Agent 迭代（标注+代码编写） → 提取结果 Excel
```

## 前置条件

- `memect_apiserver` 可用（用于 PDF→DocJSON 转换）
- PDF 文件以 hex UUID 命名（如 `2529252caee449e48d1eb74a2bd82022.pdf`）

## 步骤

### 1. 批量 PDF → DocJSON

如果已有 docjson 文件可跳过此步。

```bash
uv run python scripts/prepare_docjson.py /path/to/pdf_dir
```

参数：
- `pdf_dir`：包含 PDF 文件的目录
- `--base-url`：apiserver 地址（默认 `http://localhost:6111/api`）

输出：在 `pdf_dir/docjson/` 下生成同名 `.json` 文件。已存在的会自动跳过。

### 2. 准备 workspace

将 PDF + DocJSON 导入到 workspace 的 `.extract-dev/data/` 目录。

```bash
uv run python scripts/prepare_workspace.py \
  --source-dir /path/to/pdf_dir \
  --workspace local/workspaces/my_task
```

参数：
- `--source-dir`：PDF 源目录（需包含 `docjson/` 子目录）
- `--workspace`：目标 workspace 路径（不存在会自动创建）
- `--skip-docjson`：跳过 DocJSON 生成（源目录已有 docjson 时使用）
- `--base-url`：apiserver 地址

脚本执行三个步骤：
1. 批量 PDF→DocJSON（可通过 `--skip-docjson` 跳过）
2. 导入数据到 `workspace/.extract-dev/data/`（docjson、pdf、空标注骨架）
3. 写入占位 schema

### 3. 编写 schema 指导文件

在 workspace 下创建 `user_message.md`，告诉 Agent 要提取哪些字段。

```bash
# 手动创建，内容参考 local/prompts/ 下的 schema 定义
vim local/workspaces/my_task/user_message.md
```

文件格式示例：

```markdown
## Schema 指导：xxx

**定位章节：** 第X节 xxx

请严格按照以下 schema 进行提取，不要修改 schema 字段：

|**字段名称 (Schema Key)**|**字段定义**|**提取逻辑 / 对应关系**|
|---|---|---|
|`field_a`|**字段A**|对应表格中"xxx"的值。|
|`field_b`|**字段B**|对应"xxx"的值。|

**重要提示：**
- schema 类型为 `object`（单对象），不是 `list_of_objects`
- 所有字段值为字符串类型（`str`），提取原始数值文本
- 请使用已预设的 schema，不要自行生成新的 schema
```

这个文件的作用是约束 BusinessAgent 使用预定义的 schema，防止它自行推断出错误的字段结构。

### 4. 启动 Agent 迭代

```bash
uv run agentscope-agent run \
  --unlabeled \
  --workspace local/workspaces/my_task \
  --studio-url http://127.0.0.1:3000 \
  --reset \
  --user-message-file local/workspaces/my_task/user_message.md
```

参数说明：
- `--unlabeled`：无标注模式，BusinessAgent 先分析文档并生成标注，再由 ExtractDevAgent 编写提取代码
- `--workspace`：workspace 路径
- `--studio-url`：AS Studio 地址（可选，用于可视化监控）
- `--reset`：清除之前的 Agent 状态，从头开始
- `--user-message-file`：schema 指导文件路径

Agent 工作流程：
1. BusinessAgent 分析文档，根据 `user_message.md` 中的 schema 定义生成标注（写入 `.extract-dev/labels.json`）
2. BusinessAgent 生成 `business_guide.md`（业务指导文档）
3. ExtractDevAgent 编写 `program.py`（提取代码）
4. ExtractDevAgent 反复运行评估、修改代码，直到准确率达到 99%

### 5. 导出提取结果

Agent 完成后（或有了 `program.py` 后），可以导出 Excel：

```bash
# 默认输出到 workspace 目录下
uv run python scripts/run_extract_to_excel.py local/workspaces/my_task

# 指定输出路径
uv run python scripts/run_extract_to_excel.py local/workspaces/my_task -o /tmp/result.xlsx
```

Excel 按文档展示各字段的提取结果，字段列从 `program.py` 的返回值自动推断。

## workspace 目录结构

完成全流程后，workspace 的目录结构如下：

```
local/workspaces/my_task/
├── user_message.md              # schema 指导文件（步骤 3 手动创建）
├── program.py                   # 提取代码（Agent 生成）
├── business_guide.md            # 业务指导（BusinessAgent 生成）
├── extract_results.xlsx         # 提取结果（步骤 5 生成）
├── .extract-dev/
│   ├── data/
│   │   ├── manifest.json        # 数据源元信息
│   │   ├── schema.json          # schema 定义
│   │   ├── docjson/             # DocJSON 文件
│   │   ├── pdf/                 # PDF 文件（软链接）
│   │   └── standard_for_evaluate/
│   │       └── train.json       # 标注骨架（初始为空标注）
│   ├── labels.json              # BusinessAgent 生成的标注（覆盖层）
│   └── schema.json              # BusinessAgent 更新的 schema
├── logs/                        # Agent 运行日志
└── .agent_state/                # Agent 状态（可通过 --reset 清除）
```
