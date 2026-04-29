---
name: release-process
description: 当用户要求更新 extract-agent 版本号、补 changelog、构建 dist、推送代码、或发布到 PyPI 时使用此 skill。只用于维护者发版，不用于日常 workspace 提取。
---

# release-process

`release-process` 负责当前仓库的标准发版流程。

## 触发

当用户表达以下意图时，直接使用本 skill：

- “更新版本号然后发布”
- “build 并 publish”
- “走一遍标准发版流程”
- “发布到 PyPI”

## 规则

- 版本号必须同步更新这 3 个位置：
  - `pyproject.toml`
  - `src/xdev/__init__.py`
  - `src/agentic_extract/__init__.py`
- `docs/CHANGELOG.md` 必须记录本次版本的主要改动
- 优先跑与本次改动直接相关的验证，不要求每次全仓
- `uv build` 之后只发布当前版本对应的两个产物，不要直接发布整个 `dist/`
- 标准顺序固定为：更新版本 -> 验证 -> commit -> build -> push -> publish

## 默认执行

1. `git status`
2. 更新版本号和 `docs/CHANGELOG.md`
3. 运行必要验证
4. `git add` 本次版本涉及文件
5. `git commit -m "chore: release X.Y.Z"`
6. `uv build`
7. 检查：
   - `dist/extract_agent-X.Y.Z.tar.gz`
   - `dist/extract_agent-X.Y.Z-py3-none-any.whl`
8. `git push`
9. 发布：

```bash
uv publish \
  dist/extract_agent-X.Y.Z.tar.gz \
  dist/extract_agent-X.Y.Z-py3-none-any.whl
```

发布 token 不要写入命令或文档；通过 `UV_PUBLISH_TOKEN` 环境变量、keyring 或交互输入提供。

## 验证

常用命令：

```bash
uv run pytest -q tests/agentic_extract
uv run pytest -q tests/integration/test_suite.py -k export_skills
uv run ruff check <touched-files>
```

如果这次只改文档，至少确认命令、文件路径、版本号和链接都已更新。
