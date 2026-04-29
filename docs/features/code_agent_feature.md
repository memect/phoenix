# CodeAgent 功能实现计划

## 概述

为 `agentscope_agent` 模块添加可选的 CodeAgent 子 Agent 功能，实现任务委托模式（Handoffs）。

### 背景

当前 ExtractDevAgent 独立完成所有工作：分析问题、写代码、测试、验证。引入 CodeAgent 后：
- ExtractDevAgent：分析问题、形成假设、委托执行、验证结果
- CodeAgent：接收具体任务、实现代码优化

### 目标

1. 实现可选的 CodeAgent handoff 功能
2. 支持 `--standard-entry-ids` 参数筛选文档评估
3. 重构 prompts 目录结构

## 设计

### 架构

```
ExtractDevAgent (主 Agent)
  ↓ 分析问题，形成假设
  ↓ 调用 create_code_agent() 工具
CodeAgent (子 Agent)
  ↓ 执行具体的代码优化任务
  ↓ 返回详细结果 (JSON)
ExtractDevAgent 继续验证
```

### 工作流程

```
1. ExtractDevAgent 运行 extract-dev train
   → 发现某字段准确率低
   ↓
2. ExtractDevAgent 分析问题
   → 查看错误样本 (extract-dev run)
   → 形成假设（中等具体）
   ↓
3. ExtractDevAgent 调用 create_code_agent()
   输入：field, hypothesis, problem_analysis, error_doc_ids
   ↓
4. CodeAgent 执行
   → 读代码 → 修改 → 写测试（如需要）→ 验证
   → 返回结果 JSON
   ↓
5. ExtractDevAgent 验证
   → 运行回归测试 (pytest)
   → 运行整体评估 (extract-dev train)
   → 失败则修正假设重试
```

### 可选配置

```bash
# 默认：不启用 CodeAgent
python -m agentscope_agent --model xxx --workspace yyy

# 启用 CodeAgent（同模型）
python -m agentscope_agent --model xxx --workspace yyy --enable-code-agent

# 启用 CodeAgent（不同模型）
python -m agentscope_agent --model xxx --workspace yyy \
    --enable-code-agent --code-agent-model openai/gpt-4o-mini
```

### CodeAgent 返回格式

```json
{
    "success": true,
    "changes_summary": "在 extract_date() 中添加了 YYYY-MM-DD 格式支持",
    "tests_written": true,
    "tests_passed": true,
    "verified_doc_ids": ["doc_001", "doc_003"],
    "files_modified": ["program.py", "tests/test_date.py"],
    "error_message": null
}
```

## 实现计划

### 阶段 1：重构 prompts 目录结构

**改动**：
- 创建 `prompts/` 目录
- 拆分 `prompts.py` 为：
  - `prompts/extract_dev.py` - ExtractDevAgent prompts（两个变体）
  - `prompts/supervisor.py` - SupervisorAgent prompts
  - `prompts/code_agent.py` - CodeAgent prompts（新增）
- 更新所有导入

**文件结构**：
```
prompts/
├── __init__.py
├── extract_dev.py      # SYSTEM_PROMPT_BASE, SYSTEM_PROMPT_WITHOUT_CODE_AGENT, 
│                       # SYSTEM_PROMPT_WITH_CODE_AGENT, get_initial_message()
├── supervisor.py       # SYSTEM_PROMPT, get_initial_message()
└── code_agent.py       # SYSTEM_PROMPT
```

### 阶段 2：实现 `--standard-entry-ids` 参数

**改动模块**：
- `extract_dev/cli.py` - 添加 `--standard-entry-ids` 参数到 train/test 命令
- `evaluation_engine/api.py` - 添加 std_ids 筛选支持
- `evaluation_engine/engine.py` - 实现筛选逻辑

**CLI 用法**：
```bash
# 指定文档评估
extract-dev train --standard-entry-ids "id_001,id_003,id_005"
extract-dev train --standard-entry-ids "id_001,id_003" --key "原文_会议召开时间"

# 测试集也支持
extract-dev test --standard-entry-ids "id_001,id_002"
```

### 阶段 3：实现 CodeAgent 功能

**新增文件**：
- `agents/code_agent.py` - `create_code_agent()` 工具函数

**修改文件**：
- `agents/extract_dev.py` - 条件注册 CodeAgent 工具
- `agents/__init__.py` - 导出新函数
- `config.py` - 添加 `enable_code_agent`, `code_agent_model` 配置
- `cli.py` - 添加 CLI 参数
- `workflow.py` - 参数传递

**CodeAgent 工具集**：
- `extract-dev doc <id>` - 查看文档
- `extract-dev standard <id>` - 查看标准答案
- `extract-dev run <id>` - 单文档评估
- `extract-dev train --standard-entry-ids --key` - 指定文档和字段评估
- `view_text_file` - 读文件
- `write_text_file` - 写文件
- `execute_shell_command` - 执行命令（pytest 等）

### 阶段 4：文档更新

- `docs/agentscope_agent_design.md` - 更新模块结构、工作流程
- `docs/extract_dev_guide.md` - 添加 `--standard-entry-ids` 参数说明
- `docs/project-rules.md` - 更新模块描述
- `docs/CHANGELOG.md` - 记录更新

## 最终目录结构

```
src/agentscope_agent/
├── __init__.py
├── __main__.py
├── cli.py
├── config.py
├── model_factory.py
├── workflow.py
│
├── agents/
│   ├── __init__.py
│   ├── extract_dev.py      # ExtractDevAgent 工厂
│   ├── code_agent.py       # create_code_agent() 工具函数
│   └── supervisor.py       # SupervisorAgent 类
│
├── prompts/                # Prompts（按 Agent 组织）
│   ├── __init__.py
│   ├── extract_dev.py      # ExtractDevAgent prompts
│   ├── code_agent.py       # CodeAgent prompts
│   └── supervisor.py       # SupervisorAgent prompts
│
├── tracking/
│   ├── __init__.py
│   ├── token_stats.py
│   └── model_wrapper.py
│
└── state/
    ├── __init__.py
    ├── saver.py
    └── manager.py
```

## 配置项汇总

### 环境变量

```bash
# 现有
ASA_MODEL=gemini/gemini-2.0-flash
ASA_API_BASE=https://api.xxx.com/v1
ASA_API_KEY=xxx

# 新增
ASA_ENABLE_CODE_AGENT=false       # 默认禁用
ASA_CODE_AGENT_MODEL=             # 默认同 ASA_MODEL
```

### CLI 参数

```bash
# 现有参数保持不变

# 新增
--enable-code-agent              # 启用 CodeAgent handoff
--code-agent-model TEXT          # CodeAgent 使用的模型
```

## 测试计划

### 单元测试

1. `--standard-entry-ids` 参数解析测试
2. CodeAgent 工具函数测试
3. 配置加载测试

### 集成测试

1. 不启用 CodeAgent 时行为不变
2. 启用 CodeAgent 时工具注册正确
3. CodeAgent 返回格式正确

### 手工测试

1. 完整流程测试（启用/禁用 CodeAgent）
2. 不同模型配置测试
3. 失败重试测试

## 风险和注意事项

1. **Token 消耗**：启用 CodeAgent 会增加 Token 消耗，需在文档中说明
2. **向后兼容**：默认禁用 CodeAgent，确保现有行为不变
3. **状态隔离**：每次 CodeAgent 调用都是全新实例，不保留状态
4. **Supervisor 不变**：Supervisor 只监督 ExtractDevAgent，不监督 CodeAgent
