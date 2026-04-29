# xdev workspace

## 目标

让 workspace 处于“可以持续维护数据、持续调试提取代码”的状态。

## 初始化

默认命令：

```bash
xdev init /path/to/workspace
cd /path/to/workspace
```

如果不传参数，默认初始化到 `./workspace`。

## 最小目录心智模型

典型 workspace 会包含：

```text
workspace/
  program.py
  tests/
  docs/
  .xdev/
  .gitignore
```

运行后还会出现：

```text
workspace/
  .agent_state/
```

职责分工：

- `program.py`：提取实现
- `tests/`：针对 `program.py` 的测试
- `.xdev/`：文档数据、schema、labels、manifest、项目级配置
- `.agent_state/`：`agentic-extract` 运行时状态

`xdev` 主要维护 `.xdev/`；不要把 `.agent_state/` 当成数据目录的一部分。

## `.xdev/` 里最关键的东西

- `.xdev/schema.json`
- `.xdev/labels/<doc_id>.json`
- `.xdev/manifest.json`
- `.xdev/config.json`
- `.xdev/data/docjson/...`

## 使用规则

- 如果 workspace 已经存在且数据仍然有效，直接复用，不要重复 `init`
- 在 workspace 内工作时，优先使用默认的 `.xdev`，不必到处显式传 `--data-dir`
- `business_guide.md` 可以存在，但不是初始化前置条件
- workspace 的数据状态不是线性阶段；导入新 PDF 后，schema/标注状态可能再次变为“需要处理”
