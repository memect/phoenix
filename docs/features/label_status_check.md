# 需求：标注状态检查与 BusinessAgent 标注完整性保障

## 背景

BusinessAgent 负责定义 schema 并标注所有文档。当前存在以下问题：

1. BusinessAgent 标完一部分文档后可能就停下了，没有把所有文档都标完
2. schema 变更后，已有标注可能与新 schema 不匹配（字段增删、类型变化），但没有机制发现这个问题
3. BusinessAgent 没有手段快速了解"当前标注状态"——哪些标了、哪些没标、哪些标注和 schema 对不上

## 目标

1. 新增 `xdev label-status` CLI 命令，检查并报告当前标注状态
2. 在 xdev Python API 中提供对应函数，供批量标注工具调用
3. BusinessAgent 在标注前先检查状态，确保最终把所有文档都标完、标注都与 schema 一致

## 一、`xdev label-status` 命令

### 用法

```bash
xdev label-status              # 输出标注状态摘要
xdev label-status --detail     # 输出详细信息（列出每个问题文档）
```

### 输出示例

摘要模式：
```
标注状态:
  文档总数:       20
  已标注:         15
  未标注:          5
  Schema 不匹配:   3

结论: 有 8 篇文档需要处理（5 未标注 + 3 不匹配）
```

详细模式（`--detail`）：
```
标注状态:
  文档总数:       20
  已标注:         15
  未标注:          5
  Schema 不匹配:   3

未标注文档:
  - doc_016
  - doc_017
  - doc_018
  - doc_019
  - doc_020

Schema 不匹配文档:
  - doc_003: 缺少字段 [成立日期], 多余字段 [注册日期]
  - doc_007: 缺少字段 [成立日期]
  - doc_012: 字段类型错误 [注册资本: 期望 float, 实际 str]

结论: 有 8 篇文档需要处理（5 未标注 + 3 不匹配）
```

### 检查规则

前提：`schema.json` 必须存在，否则报错退出。

对每个已标注文档，检查以下内容：

1. **key 一致性**
   - 标注的 key 必须与 `schema.data` 的 key 完全一致
   - 报告：缺少的字段、多余的字段
   - 对 `list_of_objects` 类型，检查数组中每个元素的 key

2. **类型检查**（基础）
   - `int` 字段的值应该是 int（不是 str）
   - `float` 字段的值应该是 int 或 float（不是 str）
   - `bool` 字段的值应该是 bool
   - `list` 字段的值应该是 list
   - `str` 字段不检查（任何值都可以转为 str）
   - 空值（`""`, `null`）跳过类型检查（表示缺失信息）

3. **结构类型检查**
   - `object` 类型的 schema，标注必须是 dict
   - `list_of_objects` 类型的 schema，标注必须是 list，且每个元素是 dict

## 二、Python API

在 `xdev/api.py` 中新增：

```python
@dataclass
class LabelIssue:
    """单个标注问题"""
    doc_id: str
    issue_type: str          # "missing_fields" | "extra_fields" | "type_error" | "structure_error"
    detail: str              # 人类可读描述

@dataclass
class LabelStatusReport:
    """标注状态报告"""
    total_docs: int          # 文档总数
    labeled_count: int       # 已标注数
    unlabeled_ids: list[str] # 未标注文档 ID 列表
    mismatched_ids: list[str]  # schema 不匹配的文档 ID 列表
    issues: list[LabelIssue]   # 具体问题列表

    @property
    def unlabeled_count(self) -> int:
        return len(self.unlabeled_ids)

    @property
    def mismatched_count(self) -> int:
        return len(self.mismatched_ids)

    @property
    def needs_action_count(self) -> int:
        """需要处理的文档数（未标注 + 不匹配，去重）"""
        return len(set(self.unlabeled_ids) | set(self.mismatched_ids))

    @property
    def all_good(self) -> bool:
        return self.unlabeled_count == 0 and self.mismatched_count == 0


def check_label_status(data_dir: str | None = None) -> LabelStatusReport:
    """检查标注状态，返回报告"""
    ...
```

## 三、批量标注工具适配

当前 `label_all_documents` 工具只标注未标注的文档。需要适配：

- 新增 `relabel_doc_ids` 参数：指定需要重新标注的文档 ID（覆盖已有标注）
- BusinessAgent 的使用流程：
  1. 调用 `xdev label-status` 查看状态
  2. 如果有 schema 不匹配的文档，把这些 doc_id 传给 `label_all_documents` 的 `relabel_doc_ids` 参数
  3. 未标注的文档会自动被标注（现有逻辑）

### 工具签名变更

```python
async def label_all_documents(
    doc_ids: str = "",
    relabel_mismatched: bool = False,
) -> ToolResponse:
    """批量标注文档。

    默认标注所有未标注的文档。

    Args:
        doc_ids: 逗号分隔的文档 ID（可选，为空则标注全部未标注文档）
        relabel_mismatched: 是否同时重新标注与 schema 不匹配的文档
    """
```

当 `relabel_mismatched=True` 时：
1. 调用 `check_label_status()` 获取不匹配列表
2. 将不匹配的 doc_id 加入标注队列（会覆盖已有标注）
3. 加上未标注的文档，一起并发标注

## 四、BusinessAgent 工作流调整

在 business SKILL.md 的"第四阶段：标注数据"中，补充检查步骤：

```
### 第四阶段：标注数据

1. 运行 `xdev label-status` 检查当前标注状态
2. 如果有 schema 不匹配的文档，检查不匹配原因：
   - 如果是 schema 变更导致的，需要重新标注这些文档
   - 如果是标注错误，需要修正
3. 调用 `label_all_documents` 标注所有文档
   - 如果有不匹配文档，设置 relabel_mismatched=True
4. 标注完成后，再次运行 `xdev label-status` 确认全部通过
5. **必须确保: 所有文档都已标注且与 schema 匹配后才算完成**
```

## 实现清单

1. `src/xdev/api.py` — 新增 `LabelIssue`、`LabelStatusReport`、`check_label_status()`
2. `src/xdev/cli.py` — 新增 `label-status` 命令（`--detail` 选项）
3. `src/agentic_extract/labeling/workflow.py` — `label_all_documents` 新增 `relabel_mismatched` 参数
4. `src/agentic_extract/skills/xdev/SKILL.md` — 文档补充 `label-status` 命令说明
5. `src/agentic_extract/skills/business/SKILL.md` — 标注阶段补充检查步骤
