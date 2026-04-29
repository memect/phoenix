# Evaluator 模块重构计划

## 当前状态

> 更新于 2026-01-09

**阶段 1 待执行** - 以下文件仍存在，需要删除：
- [ ] `evaluator/shotcut.py` - 旧版快捷接口
- [ ] `evaluator/examples.py` - 示例代码
- [ ] `evaluators/object/factory.py` - DataCreator 实现
- [ ] `evaluators/list_of_objects/factory.py` - DataCreator 实现
- [ ] `standards/document_manager.py` - 文档管理器

**阶段 2 待执行** - 合并后可删除：
- [ ] `evaluators/extended/` 整个目录 - 需先合并到基础评估器

**依赖关系问题（需要先解决）：**
- `api.py` 依赖 `shortcuts.py` 的 `get_evaluate_parts` 和 `EvaluateParts`
- `shortcuts.py` 依赖 `factory.py` 的 `ObjectEvaluatorDataCreator` 和 `ListOfObjectsEvaluatorDataCreator`
- `evaluator_factory.py` 依赖 `evaluators/extended/` 的 `ExtendedObjectEvaluator` 和 `ExtendedListOfObjectsEvaluator`
- `manager.py` 依赖 `document_manager.py` 的 `DocumentManager`

**待清理的代码问题：**
- [ ] `core/base.py` 中存在未使用的导入 (`EvaluationStandard`, `EvaluationExtraction`)
- [ ] `core/base.py` 中 `DataCreator` 类待删除（但 `shortcuts.py` 仍在使用）
- [ ] `shortcuts.py` 中 `create_standard_set_manager` 和 `load_all_standard_sets` 调用了不存在的方法

---

## 目标

剔除 `src/evaluator` 模块中未被 `simple_workflow` 使用的多余功能，简化代码结构。

## 背景

当前 `evaluator` 模块包含了很多未被实际使用的功能和复杂的层级结构。通过分析发现：
- `simple_workflow` 通过 `evaluation_engine` 间接使用 `evaluator`
- 很多便捷接口和示例代码未被使用
- 评估器有三层包装（基础 → 扩展 → 绑定数据集），过于复杂

## 使用情况分析

### 被使用的组件

**simple_workflow/main.py:**
- `evaluator.standards.SchemaType`
- `evaluator.standards.dataset_app.generate_dataset`
- `evaluator.core.models.EvaluationResult`

**simple_workflow/workflow.py:**
- `evaluator.core.models.EvaluationResult`

**evaluation_engine/engine.py:**
- `evaluator.standards.manager.StandardSetManager`
- `evaluator.standards.models.StandardSet, StandardSetMetadata, FullSchema`
- `evaluator.core.evaluation_models.FullStandard, FullExtractedResult`
- `evaluator.core.models.EvaluationResult, RecordDetailBase`

### 未被使用的组件

- `api.py` - ✅ 保留（提供独立的评估接口，但需要重构以移除对 shortcuts 的依赖）
- `cli.py` - ✅ 保留（提供 CLI 命令）
- `shortcuts.py` - ⚠️ 重构（`api.py` 依赖它，需要将必要功能迁移到 `api.py` 后删除）
- `shotcut.py` - ❌ 删除（旧版）
- `examples.py` - ❌ 删除
- `evaluators/extended/` - ⚠️ 合并后删除（`evaluator_factory.py` 依赖它）
- `evaluators/object/factory.py` - ⚠️ 重构后删除（`shortcuts.py` 依赖 DataCreator）
- `evaluators/list_of_objects/factory.py` - ⚠️ 重构后删除（`shortcuts.py` 依赖 DataCreator）
- `standards/document_manager.py` - ⚠️ 重构后删除（`manager.py` 依赖它）
- `core/base.py` 中的 `DataCreator` - ⚠️ 重构后删除（`shortcuts.py` 依赖它）

## 重构计划

### 阶段 1：删除未使用的文件（无依赖）

删除以下文件（这些文件没有被其他代码依赖）：

```
evaluator/
├── shotcut.py              # 旧版快捷接口，已被 shortcuts.py 替代
└── examples.py             # 示例代码，未被引用
```

### 阶段 1.5：重构 api.py，移除对 shortcuts.py 的依赖

**目标：** 让 `api.py` 直接使用评估器，不再依赖 `shortcuts.py`

**具体改动：**
1. 将 `shortcuts.py` 中的 `EvaluateParts` 移动到 `api.py`
2. `api.py` 直接导入 `ObjectEvaluator` 和 `ListOfObjectsEvaluator`
3. 移除 `api.py` 对 `DataCreator` 的依赖（`api.py` 实际上不需要 DataCreator）

**完成后可删除：**
- `evaluator/shortcuts.py`

### 阶段 1.6：重构 manager.py，移除对 document_manager.py 的依赖

**目标：** 评估 `DocumentManager` 是否真正需要

**分析：**
- `DocumentManager` 用于按 ID 索引文档
- 如果 `simple_workflow` 不使用这个功能，可以删除
- 如果需要保留，考虑简化或内联到 `manager.py`

**完成后可删除：**
- `standards/document_manager.py`

### 阶段 2：简化评估器层级

**目标：** 合并基础评估器和扩展评估器

**当前三层结构：**
```
evaluators/object/ObjectEvaluator (基础)
    ↓ 被包装
evaluators/extended/ExtendedObjectEvaluator (扩展)
    ↓ 被包装
standards/evaluator_factory.DatasetBoundEvaluator (绑定数据集)
```

**简化后两层结构：**
```
evaluators/object/ObjectEvaluator (合并后)
    ↓ 被包装
standards/evaluator_factory.DatasetBoundEvaluator (绑定数据集)
```

**依赖分析：**
- `evaluator_factory.py` 直接使用 `ExtendedObjectEvaluator` 和 `ExtendedListOfObjectsEvaluator`
- 合并后需要更新 `evaluator_factory.py` 的导入

**具体改动：**

1. **合并 `ObjectEvaluator`**
   - 将 `ExtendedObjectEvaluator` 的逻辑合并到 `ObjectEvaluator`
   - 直接支持 `FullStandard` / `FullExtractedResult` 作为输入
   - 输出使用合并后的 `RecordDetail` 和 `ObjectEvaluationResult`

2. **合并 `ObjectEvaluationResult` 模型**
   - 将 `ExtendedRecordDetail` 合并到 `RecordDetail`
   - 将 `ExtendedObjectEvaluationResult` 合并到 `ObjectEvaluationResult`
   - `RecordDetail` 直接使用 `FullStandard` / `FullExtractedResult`

3. **同样处理 `ListOfObjectsEvaluator`**

4. **更新 `evaluator_factory.py`**
   - 改为导入合并后的 `ObjectEvaluator` 和 `ListOfObjectsEvaluator`

**完成后可删除：**
```
evaluators/extended/                    # 整个目录
├── __init__.py
├── object_evaluator.py
├── object_models.py
├── list_of_objects_evaluator.py
├── list_of_objects_models.py
└── models.py
```

### 阶段 2.5：删除 DataCreator 相关代码

**前置条件：** 阶段 1.5 完成后，`shortcuts.py` 已删除

**删除文件：**
```
evaluators/object/factory.py
evaluators/list_of_objects/factory.py
```

**更新文件：**
- `core/base.py` - 删除 `DataCreator` 类
- `core/__init__.py` - 删除 `DataCreator` 导出
- `evaluators/object/__init__.py` - 删除 `DataCreator` 导出
- `evaluators/list_of_objects/__init__.py` - 删除 `DataCreator` 导出

### 阶段 3：统一数据模型

**保留基类定义（作为继承基础）：**
- `core/evaluation_models.py` 中的 `EvaluationStandard` - 保留，是 `FullStandard` 的基类
- `core/evaluation_models.py` 中的 `EvaluationExtraction` - 保留，是 `FullExtractedResult` 的基类

**统一使用完整版（在业务代码中）：**
- `FullStandard` - 替代直接使用 `EvaluationStandard`
- `FullExtractedResult` - 替代直接使用 `EvaluationExtraction`

**清理未使用的导入：**
- `core/base.py` 中删除未使用的 `EvaluationStandard`, `EvaluationExtraction` 导入

### 阶段 4：更新依赖模块

**需要更新的文件：**

```
evaluator/
├── __init__.py               # 更新导出
├── api.py                    # 直接使用评估器，不再依赖 shortcuts
├── core/
│   ├── __init__.py           # 删除 DataCreator 导出
│   ├── base.py               # 删除 DataCreator 类和未使用的导入，保留 Evaluator
│   ├── models.py             # RecordDetailBase 使用 FullStandard/FullExtractedResult
│   └── evaluation_models.py  # 保留 EvaluationStandard/EvaluationExtraction（作为基类）
├── evaluators/
│   ├── __init__.py           # 更新导出
│   ├── object/
│   │   ├── __init__.py       # 删除 DataCreator 导出
│   │   ├── object_evaluator.py  # 合并 Extended 逻辑
│   │   └── models.py         # 合并 Extended 模型
│   └── list_of_objects/
│       ├── __init__.py       # 删除 DataCreator 导出
│       ├── list_of_objects_evaluator.py  # 合并 Extended 逻辑
│       └── models.py         # 合并 Extended 模型
└── standards/
    ├── __init__.py           # 删除 DocumentManager 导出
    ├── evaluator_factory.py  # 使用合并后的评估器
    └── manager.py            # 删除 DocumentManager 引用

evaluation_engine/
└── engine.py                 # 删除 EvaluationStandard/EvaluationExtraction 引用
```

## 保留的功能

- ✅ `api.py` - 提供 `compare()`, `compare_objects()`, `compare_list_of_objects()` 等便捷函数（重构后）
- ✅ `cli.py` - 提供 `evaluator compare` CLI 命令
- ✅ `core/base.py` - 保留 `Evaluator` 抽象类（被评估器继承）
- ✅ `core/schema.py` - Schema 定义
- ✅ `core/evaluation_models.py` - 保留 `EvaluationStandard`, `EvaluationExtraction`, `FullStandard`, `FullExtractedResult`
- ✅ `standards/dataset_app.py` - 数据集下载功能
- ✅ `standards/loader/` - 数据加载器
- ✅ `standards/evaluator_factory.py` - 数据集评估器工厂（更新导入后）
- ✅ `standards/manager.py` - 标准集管理器（移除 DocumentManager 依赖后）
- ✅ `utils.py` - 值比较工具函数

## 执行顺序

1. **阶段 1** - 删除无依赖的文件（`shotcut.py`, `examples.py`）
2. **阶段 1.5** - 重构 `api.py`，移除对 `shortcuts.py` 的依赖，然后删除 `shortcuts.py`
3. **阶段 1.6** - 评估并处理 `document_manager.py` 的依赖
4. **阶段 2** - 合并评估器层级，然后删除 `evaluators/extended/`
5. **阶段 2.5** - 删除 `DataCreator` 相关代码（`factory.py` 文件和 `base.py` 中的类）
6. **阶段 3** - 统一数据模型，清理未使用的导入
7. **阶段 4** - 更新所有 import 和导出
8. 运行测试确保功能正常

## 预期效果

- 代码量减少约 30%
- 层级结构从三层简化为两层
- 数据模型统一，减少转换逻辑
- 保留所有实际使用的功能
- 保留独立的 API 和 CLI 接口
