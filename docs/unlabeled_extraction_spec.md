# 无标注提取：双 Agent 协作系统需求规格

## 1. 目标

实现一个**无标注场景**下的文档信息提取系统。基于现有 agentscope_agent 架构，**业务 Agent** 和 **提取 Agent** 在 Supervisor 协调下协作：业务 Agent 负责理解文档、生成 schema 和本地标注，提取 Agent 负责执行提取和优化。

## 2. 整体流程

```
用户输入：标准集 ID（作为文档数据源，不使用其标注）
         ↓
┌──────────────────────────────────────────┐
│  pseudo-init（自动）                      │
│  下载标准集到 .cache，创建 .extract-dev/   │
└──────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────┐
│  业务 Agent（Phase 1: 初始化）             │
│  1. 从文档中采样最多 20 篇观察             │
│  2. 生成：                                │
│     a. schema.json（extract-dev set-schema）│
│     b. business_guide.md（业务指导文档）   │
│  3. 调用 label_all_documents() 并发标注    │
│     → LabelingAgent × N 并发（最多16）     │
│     → 自动标注 train + test 全部文档       │
└──────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────┐
│  提取 Agent（优化循环）                    │
│  参考 schema + business_guide.md           │
│  用本地标注数据驱动 extract-dev train 评估   │
│  迭代优化 program.py                      │
└──────────────────────────────────────────┘
         ↓ Supervisor 判断
┌──────────────────────────────────────────┐
│  [BUSINESS] → 业务 Agent 修正             │
│  修正 schema / 本地标注 / business_guide.md  │
│  [CONTINUE] → 提取 Agent 继续优化         │
│  [DONE] → 任务完成                        │
└──────────────────────────────────────────┘
         ↓
       输出最终提取程序 + schema + 业务指导
```

## 3. 业务 Agent 职责

### 3.1 输入

- 标准集 ID（通过 `extract-dev` 命令访问文档数据）
- 用户的提取需求描述（自然语言，可选）

### 3.2 输出三件套

#### a. schema.json

通过 `extract-dev set-schema` 写入 `.extract-dev/schema.json`：

```json
{
    "type": "object",
    "data": {
        "字段名1": "str",
        "字段名2": "int",
        "字段名3": "list"
    }
}
```

- `type` 取值：`"object"` 或 `"list_of_objects"`
- `data` 中的类型取值：`"str"`, `"int"`, `"float"`, `"bool"`, `"list"`
- schema 是**扁平的一层结构**，不支持嵌套

**Schema 类型说明**：

| 类型 | 场景 | 标注格式 |
|------|------|----------|
| `object` | 每篇文档提取一条记录 | `{"字段1": "值1", "字段2": "值2"}` |
| `list_of_objects` | 每篇文档提取多条记录（如多个股东、多笔交易） | `[{"字段1": "值1"}, {"字段1": "值2"}]` |

选择标准：文档中同类信息只有一条 → `object`；有多条重复结构的同类信息 → `list_of_objects`

#### b. 本地标注数据

通过 `extract-dev label` 逐个写入 `.extract-dev/labels.json`：

```json
[
    {
        "id": "文档唯一标识",
        "labels": {
            "字段名1": "值1",
            "字段名2": 123
        }
    }
]
```

- `id` 必须与文档标识一致
- `labels` 的 key 必须与 schema.data 的 key 完全一致

#### c. business_guide.md

业务指导文档，放在 workspace 根目录。内容包括：

- **字段定义**：每个字段的含义、数据类型、取值范围
- **提取规则**：在文档中如何定位信息、优先级规则、冲突处理
- **边界情况**：缺失值处理、格式归一化规则
- **示例**：典型的文档片段 → 提取结果对照

### 3.3 采样策略

- 从文档集中采样**最多 20 篇**文档
- 业务 Agent 需要阅读文档全文来生成准确的本地标注

## 4. 提取 Agent 职责

### 4.1 输入

- schema（通过 `extract-dev schema` 获取，覆盖层优先）
- business_guide.md（业务指导文档）
- 本地标注数据（通过 `extract-dev train` 驱动评估）

### 4.2 优化循环

复用现有的 ExtractDevAgent 工作流，用本地标注数据驱动 `extract-dev train` 进行迭代优化。

当覆盖层 schema 存在时，`extract-dev train` 自动只评估已标注的文档。

### 4.3 反馈机制

提取 Agent 通过 `ask_business_agent` 工具向业务 Agent 提问，或由 Supervisor 判断 `[BUSINESS]` 触发业务 Agent 介入。典型场景：

- schema 字段与文档内容不匹配
- 本地标注与文档内容矛盾
- 准确率无法继续提升

## 5. 协作循环与终止条件

### 5.1 终止条件（对齐 agentscope_agent）

满足任一即停：

1. **所有字段 F1 >= target_accuracy**（默认 0.99）→ Supervisor 输出 `[DONE]`
2. **Supervisor 判断无法继续优化** → 输出 `[DONE]`
3. **达到 max_iterations**（默认 50）
4. **run_timeout 超时**

### 5.2 Supervisor 决策

每轮迭代后，Supervisor 检查进度并输出：

- `[DONE]` — 任务完成
- `[BUSINESS]` — 需要业务 Agent 修正 schema/标注/指导文档
- `[CONTINUE]` — 提取 Agent 继续优化
- 建议文本 — 给提取 Agent 的具体指导

### 5.3 业务 Agent 修正逻辑

收到 `[BUSINESS]` 触发后，业务 Agent：

1. 分析当前评估结果和提取 Agent 的反馈
2. 修正 schema（`extract-dev set-schema`）
3. 修正本地标注（`extract-dev label`）
4. 更新 `business_guide.md`

## 6. extract-dev 工具链

### 6.1 覆盖层机制

本地标注数据存储在 `workspace/.extract-dev/` 目录，优先级高于 `.cache` 中的标准集数据：

```
workspace/.extract-dev/
├── schema.json       # 业务 Agent 生成的 schema
└── labels.json       # 业务 Agent 生成的本地标注
```

**优先级规则**：
- `extract-dev schema` → `.extract-dev/schema.json` 优先
- `extract-dev standard <doc_id>` → `.extract-dev/labels.json` 中的条目优先
- `extract-dev train` → 覆盖层 schema 存在时，只评估已标注的文档
- `extract-dev doc` → 始终从 `.cache`（文档本身不覆盖）

### 6.2 新增命令

| 命令 | 功能 |
|------|------|
| `extract-dev pseudo-init --set-id <id>` | 下载标准集到缓存，创建 `.extract-dev/` |
| `extract-dev set-schema '<json>'` | 写入 `.extract-dev/schema.json` |
| `extract-dev label <doc_id> '<json>'` | 追加/更新 `.extract-dev/labels.json` |
| `extract-dev labels` | 查看所有本地标注 |
| `extract-dev reset-labels` | 清空本地标注 |

### 6.3 标准集目录结构（.cache）

```
.cache/{set_id}/
├── train/
│   ├── schema.json
│   ├── standard_for_evaluate/
│   │   └── train.json
│   ├── docjson/
│   │   └── {hex_id}.json
│   └── pdf/
│       └── {hex_id}.pdf
└── test/
```

### 6.4 labels.json 格式

```json
[
    {
        "id": "9dc46ebb-e756-750c-78b9-11a96b7dbc1c",
        "labels": {
            "会议召开地点": "北京市海淀区西三环北路87号国际财经中心D座503公司会议室",
            "会议召开时间": "2025-05-16 14:30:00"
        }
    }
]
```

## 7. agentscope_agent 架构变更

### 7.1 BusinessAgent 默认启用

- 去掉 `--no-supervisor` 选项，Supervisor + BusinessAgent 始终启用
- 去掉 `--enable-business-agent` 选项，BusinessAgent 默认开启
- BusinessAgent 拥有命令行工具权限，可直接调用 `extract-dev` 命令

### 7.2 BusinessAgent 新增能力

除了现有的"生成 business_guide.md"和"回答业务问题"，BusinessAgent 还能：

- 调用 `extract-dev set-schema` 定义 schema
- 调用 `extract-dev label` 标注文档
- 调用 `extract-dev labels` 查看已标注数据
- 调用 `extract-dev reset-labels` 清空标注

### 7.3 workflow 启动流程

```
agentscope-agent run --set-id <id>
    ↓
1. 创建 workspace，设置环境变量
2. 创建 Supervisor（含 BusinessAgent）
3. 业务 Agent 生成 business_guide.md + schema + 本地标注
4. 创建 ExtractDevAgent
5. Supervisor 协调的对话循环
6. 终止 → 自动提交 workspace
```

## 8. 关键设计约束

1. **业务 Agent 生成的所有产物必须严格兼容评估器格式**
2. **schema 只支持扁平一层**——不支持嵌套字段
3. **本地标注的 id 必须与文档 id 一致**——评估器通过 id 匹配
4. **本地标注的 labels key 必须与 schema.data key 完全一致**
5. **提取 Agent 可以通过 Supervisor 触发业务 Agent 修正标注**
6. **覆盖层 schema 存在时，评估只用已标注文档**

## 9. LabelingAgent 并发标注

### 9.1 概述

无标注模式下，BusinessAgent 完成 schema 和 business_guide.md 后，通过 `label_all_documents()` 工具触发并发标注。每篇文档由独立的 LabelingAgent 实例处理，最多 16 并发。

### 9.2 架构

```
BusinessAgent
  └── label_all_documents() 工具
        ├── LabelingAgent(doc_id="t1", dataset="train") ─┐
        ├── LabelingAgent(doc_id="t2", dataset="train") ─┤ asyncio.Semaphore(16)
        ├── LabelingAgent(doc_id="e1", dataset="test")  ─┘
        └── ...
```

### 9.3 LabelingAgent

- 每次调用 `label_document()` 创建独立的 `ReActAgent` 实例
- 使用独立的 LLM 配置（`ASA_LABELING_MODEL/API_BASE/API_KEY`）
- 提示词根据 schema type 动态生成格式提示（object vs list_of_objects）
- 命令包含 `--dataset train/test` 参数

### 9.4 配置

环境变量（`.agentscope_agent.env`）：

```
ASA_LABELING_MODEL=deepseek/deepseek-v4-flash
ASA_LABELING_API_BASE=https://api.deepseek.com/v1
ASA_LABELING_API_KEY=sk-xxx
```

CLI 参数：`--labeling-model`, `--labeling-api-base`, `--labeling-api-key`

### 9.5 工具接口

```python
# 标注全部文档
await label_all_documents()

# 重试指定文档
await label_all_documents(doc_ids="t1,e2")
```

返回 `ToolResponse`，包含成功/失败统计和失败文档 ID 列表。

## 10. 非功能性要求

- 每轮迭代都有清晰的日志记录（`logs/` 目录）
- 业务 Agent 的 business_guide.md 应该是人类可读的，方便人工审查
- 支持断点恢复（SessionManager 保存/恢复状态）
