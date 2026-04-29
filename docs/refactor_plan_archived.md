# 项目重构计划（已完成）

> 此文档记录了项目模块化重构的计划，重构已于 2026 年 1 月完成。
> 详细的需求和设计文档请参考 `.kiro/specs/modular-refactor/` 目录。

## 重构目标

将项目重构为模块化架构，保留 simple_workflow 核心功能，删除不相关的前后端代码，所有模块提供 CLI 和代码接口。

## 最终模块结构

```
src/
├── simple_workflow/          # 核心工作流模块
├── evaluator/                # 评估模块（纯评估逻辑）
├── code_executor/            # 代码执行模块（纯执行逻辑）
├── evaluation_engine/        # 评估引擎模块（组合执行+评估）
├── langchain_llm/            # LLM 客户端（保留）
└── memect_apiserver/         # API 服务（保留）

tests/
├── simple_workflow/
├── evaluator/
├── code_executor/
└── evaluation_engine/
```

## 模块职责与依赖关系

```
simple_workflow
    └── evaluation_engine
            ├── code_executor
            └── evaluator

langchain_llm (独立)
memect_apiserver (独立)
```

| 模块 | 职责 | 依赖 |
|------|------|------|
| `code_executor` | 执行提取代码，返回提取结果 | 无 |
| `evaluator` | 比较提取结果和标准答案，计算准确率 | 无 |
| `evaluation_engine` | 组合执行+评估，管理数据集，提供便捷接口 | code_executor, evaluator |
| `simple_workflow` | 迭代优化工作流 | evaluation_engine, langchain_llm |
| `langchain_llm` | LLM 客户端封装 | 无 |
| `memect_apiserver` | 获取 docjson | 无 |

## CLI 入口点

```toml
[project.scripts]
simple-workflow = "simple_workflow.cli:app"
evaluation-engine = "evaluation_engine.cli:app"
code-executor = "code_executor.cli:app"
evaluator = "evaluator.cli:app"
```

## 相关文档

- 需求文档: `.kiro/specs/modular-refactor/requirements.md`
- 设计文档: `.kiro/specs/modular-refactor/design.md`
- 任务列表: `.kiro/specs/modular-refactor/tasks.md`
