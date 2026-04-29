# workspace 简短使用流程

## 基本原则

- `workspace` 是长期使用的工作目录，不是一次性运行目录。
- `xdev` 负责准备和维护 `.xdev` 数据。
- `agentic-extract` 负责基于当前 workspace 做迭代。
- 日常推荐流程是：先用 `xdev` 管数据，再用 `agentic-extract run` 做迭代。
- `agentic-extract auto` 只是一键入口，适合首次 bootstrap 或外部程序调用。

## 1. 创建 workspace

```bash
xdev init --workspace /path/to/workspace
```

初始化后，workspace 通常会包含：

- `program.py`
- `tests/`
- `docs/`
- `.xdev/`
- `.gitignore`

说明：

- `.xdev/` 是数据目录。
- `.agent_state/` 会在运行时自动生成。
- `business_guide.md` 不要求预先存在，后续可以由流程补充。

## 2. 首次导入数据

从远程标准集导入：

```bash
xdev import-data --set-id <id> --data-dir /path/to/workspace/.xdev
```

从本地 PDF 目录导入：

```bash
xdev import-data --pdfs /path/to/pdfs --data-dir /path/to/workspace/.xdev
```

从另一个 `.xdev` 复制数据：

```bash
xdev import-data --from-data-dir /path/to/other/.xdev --data-dir /path/to/workspace/.xdev
```

## 3. 后续维护数据

增量添加 PDF：

```bash
xdev import-data --add-pdf /path/to/new.pdf --data-dir /path/to/workspace/.xdev
```

同步一个长期维护的 PDF 目录：

```bash
xdev sync-pdfs /path/to/pdfs --data-dir /path/to/workspace/.xdev
```

## 4. 迭代运行

当 workspace 已经有可运行的 `.xdev` 数据后，使用：

```bash
agentic-extract run --workspace /path/to/workspace
```

这是日常推荐入口。

运行过程中：

- 提取代码主要在 `program.py`
- 数据和标注主要在 `.xdev/`
- 运行内部状态在 `.agent_state/`

如果只想清空运行状态后重新开始当前迭代，可以使用：

```bash
agentic-extract run --workspace /path/to/workspace --reset
```

`--reset` 只清运行状态，不删除 `.xdev` 数据。

## 5. 一键入口

如果希望“自动准备数据并直接开始跑”，可以使用：

```bash
agentic-extract auto --workspace /path/to/workspace --set-id <id>
```

或者使用高层 Python API：

- `run_agentic_extract_auto()`

适用场景：

- 首次 bootstrap
- 外部程序一键调用
- 不想把“导数据”和“运行”分成两步时

## 推荐心智模型

- `workspace` 是长期目录。
- `xdev` 管数据。
- `agentic-extract run` 管迭代。
- `agentic-extract auto` 只是 one-click 入口。
