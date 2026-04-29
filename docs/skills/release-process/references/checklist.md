Status: active
Audience: maintainers
Last verified: 2026-04-23
Source of truth:
- pyproject.toml
- src/xdev/__init__.py
- src/agentic_extract/__init__.py

# 发布检查清单

这个清单只记录当前仓库的标准发版流程。

## 1. 更新代码和文档

- 完成功能修改
- 更新相关文档
- 更新 `docs/CHANGELOG.md`

## 2. 更新版本号

每次发布都同步修改这 3 个位置：

```toml
# pyproject.toml
[project]
version = "X.Y.Z"
```

```python
# src/xdev/__init__.py
__version__ = "X.Y.Z"
```

```python
# src/agentic_extract/__init__.py
__version__ = "X.Y.Z"
```

## 3. 运行必要验证

优先跑和本次改动直接相关的检查，不要求每次都跑全仓。

常用命令：

```bash
uv run pytest -q tests/agentic_extract
uv run pytest -q tests/integration/test_suite.py -k export_skills
uv run ruff check <touched-files>
```

如果这次改动只涉及文档，至少确认链接、命令、版本号和文件路径都已经更新。

## 4. 提交发布版本

```bash
git status
git add pyproject.toml src/xdev/__init__.py src/agentic_extract/__init__.py docs/CHANGELOG.md
git add <other-touched-files>
git commit -m "chore: release X.Y.Z"
```

## 5. 构建发布产物

```bash
uv build
```

确认当前版本的两个产物都存在：

```bash
ls dist/extract_agent-X.Y.Z.tar.gz
ls dist/extract_agent-X.Y.Z-py3-none-any.whl
```

## 6. 推送代码

```bash
git push
```

## 7. 发布到 PyPI

只发布当前版本的两个文件，不要直接发布整个 `dist/` 目录。

原因：这个仓库的 `dist/` 会保留历史版本产物，如果直接发布 `dist/*`，很容易把旧版本一起传上去。

发布 token 不要写入命令或文档；请通过 `UV_PUBLISH_TOKEN` 环境变量、keyring 或交互输入提供。

标准命令：

```bash
uv publish \
  dist/extract_agent-X.Y.Z.tar.gz \
  dist/extract_agent-X.Y.Z-py3-none-any.whl
```

## 8. 发布前最终确认

发布前确认：

- `docs/CHANGELOG.md` 已更新
- 版本号 3 处一致
- 必要验证已通过
- 已生成 `dist/extract_agent-X.Y.Z.tar.gz`
- 已生成 `dist/extract_agent-X.Y.Z-py3-none-any.whl`
- `git push` 已完成
- `uv publish` 只指向当前版本文件
