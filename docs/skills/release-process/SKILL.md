---
name: release-process
description: 当用户要求更新 extract-agent 版本号、补 changelog、构建 dist、推送代码、或发布到 PyPI 时使用此 skill。只用于维护者发版，不用于日常 workspace 提取。
---

# release-process

`release-process` 只负责当前仓库的标准发版流程。

优先在这些场景使用本 skill：

- 准备发布新的 `extract-agent` 版本
- 需要统一执行“版本号更新 + 验证 + build + push + publish”
- 需要核对当前版本对应的 wheel / sdist 是否正确

不要把下面这些事放在本 skill 里：

- 日常 `xdev` / `agentic-extract` / `pdf-ai-explorer` 使用指导
- workspace 数据准备或提取流程
- 独立的业务开发工作流

## 先做检查

- 先读 [references/checklist.md](references/checklist.md)
- 先看 `git status`，确认当前待发改动范围
- 先确认版本号会同步更新这 3 个位置：
  - `pyproject.toml`
  - `src/xdev/__init__.py`
  - `src/agentic_extract/__init__.py`
- 先确认 `docs/CHANGELOG.md` 已记录本次版本的主要改动

## 工作原则

- 版本号 3 处必须一致
- 优先跑与本次改动直接相关的验证，不要求每次全仓
- `uv build` 之后只发布当前版本对应的两个产物，不要直接传整个 `dist/`
- 标准顺序是：更新版本 -> 验证 -> commit -> build -> push -> publish

## 最短路径

1. 更新版本号与 `docs/CHANGELOG.md`
2. 运行必要验证
3. `git add` 本次版本涉及文件并提交 `chore: release X.Y.Z`
4. `uv build`
5. 检查：
   - `dist/extract_agent-X.Y.Z.tar.gz`
   - `dist/extract_agent-X.Y.Z-py3-none-any.whl`
6. `git push`
7. 发布：

```bash
uv publish \
  dist/extract_agent-X.Y.Z.tar.gz \
  dist/extract_agent-X.Y.Z-py3-none-any.whl
```

发布 token 不要写入命令或文档；通过 `UV_PUBLISH_TOKEN` 环境变量、keyring 或交互输入提供。
