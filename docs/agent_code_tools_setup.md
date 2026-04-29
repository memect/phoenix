# Agent 代码质量工具安装说明

本文档说明 agentscope-agent 依赖的命令行工具及其安装方式。

## 依赖工具列表

Agent 可以使用以下工具来提高代码质量：

| 工具 | 用途 | 必需 |
|------|------|------|
| ruff | Python linter 和格式化工具 | 是 |
| tree-sitter | 代码结构分析（通过 tree_sitter_cli） | 否 |
| mypy | 静态类型检查 | 否 |
| pytest | 测试框架 | 是 |
| pytest-cov | 测试覆盖率 | 否 |

## 安装方式

### 方式 1：使用项目依赖（推荐）

所有工具已添加到 `pyproject.toml`，同步依赖即可：

```bash
uv sync
```

### 方式 2：单独安装

如果需要单独安装：

```bash
# Ruff
pip install ruff

# Tree-sitter（用于 tree_sitter_cli）
pip install tree-sitter tree-sitter-python

# Mypy
pip install mypy

# Pytest 和覆盖率
pip install pytest pytest-cov
```

## 验证安装

### Ruff

```bash
ruff --version
# ruff 0.8.x

ruff check --help
```

### Tree-sitter CLI

```bash
tree-sitter-cli --help
# 应显示 analyze, find-symbol, list-symbols 命令
```

### Mypy

```bash
mypy --version
# mypy 1.x.x
```

### Pytest

```bash
pytest --version
# pytest 9.x.x
```

## 工具配置

### Ruff 配置

可以在 `pyproject.toml` 中添加 ruff 配置：

```toml
[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I"]
ignore = ["E501"]  # 忽略行太长
```

### Mypy 配置

可以在 `pyproject.toml` 中添加 mypy 配置：

```toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
```

## 工作原理

### 自动代码检查 (Ruff Check Hook)

当 Agent 使用 `write_text_file` 或 `insert_text_file` 写入 `.py` 文件时，会通过 `post_acting` hook 自动运行 `ruff check`。

工作流程：
1. 工具执行完成，文件写入成功
2. Hook 检测到是 `.py` 文件，运行 `ruff check`
3. 如果发现问题，创建 system 消息注入到 Agent 的 memory
4. Agent 在下一轮推理时能看到检查结果

示例输出：
```
[自动代码检查] 发现 2 个问题：
  - line 4: F401 `module.unused` imported but unused [可自动修复]
  - line 10: E501 Line too long (120 > 88)
提示：运行 `ruff check --fix <file>` 可自动修复 1 个问题
```

### Tree-sitter CLI

Tree-sitter CLI 是一个基于 tree-sitter 库的命令行工具，提供：

- `analyze`: 分析文件结构，返回省略函数体的代码骨架
- `find-symbol`: 查找符号定义位置
- `list-symbols`: 列出文件中所有符号

详细使用方法见 [tool_tree_sitter_cli.md](tool_tree_sitter_cli.md)。

## 注意事项

1. **Ruff 未安装时**：自动检查会静默跳过，不影响文件写入
2. **Tree-sitter 未安装时**：tree-sitter-cli 命令会报错
3. **Workspace 独立环境**：后续可能需要在每个 workspace 安装独立环境
