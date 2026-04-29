"""Workspace/setup helpers extracted from the legacy loop module."""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def normalize_workspace_data(workspace_path: Path | str) -> None:
    """Normalize an existing workspace into a runnable .xdev layout."""
    workspace_path = Path(workspace_path)

    from xdev.api import save_manifest
    from xdev.migrate import migrate_legacy_workspace
    from xdev.models import DataSourceDataDir, Manifest

    migrate_legacy_workspace(workspace_path)

    xdev_dir = workspace_path / ".xdev"
    manifest = xdev_dir / "manifest.json"
    if manifest.exists():
        return

    docjson_dir = xdev_dir / "data" / "docjson"
    if docjson_dir.exists() and any(docjson_dir.glob("*.json")):
        doc_count = len(list(docjson_dir.glob("*.json")))
        logger.info("检测到已有 %d 个 docjson 但缺少 manifest，自动生成", doc_count)
        manifest_data = Manifest(
            source=DataSourceDataDir(path=str(docjson_dir)),
            imported_at=datetime.now().isoformat(),
            doc_count=doc_count,
        )
        save_manifest(manifest_data, str(xdev_dir))


def workspace_has_runnable_data(workspace_path: Path | str, *, allow_normalize: bool = False) -> bool:
    """Return whether the workspace has runnable xdev data."""
    workspace_path = Path(workspace_path)

    if allow_normalize:
        normalize_workspace_data(workspace_path)

    xdev_dir = workspace_path / ".xdev"
    manifest_path = xdev_dir / "manifest.json"
    docjson_dir = xdev_dir / "data" / "docjson"
    return manifest_path.exists() and docjson_dir.exists() and any(docjson_dir.glob("*.json"))


def ensure_workspace_ready(workspace_path: Path | str, *, allow_normalize: bool = True) -> None:
    """Ensure the workspace contains runnable xdev data."""
    workspace_path = Path(workspace_path)

    if not workspace_has_runnable_data(workspace_path, allow_normalize=allow_normalize):
        raise ValueError(
            "workspace 缺少可运行的 .xdev 数据；请先使用已准备好的 workspace，"
            "或在后续使用高层 auto/prepare 入口完成数据 bootstrap。"
        )


def init_workspace(workspace_path: Path | str) -> None:
    """Initialize workspace files and git repository."""
    workspace_path = Path(workspace_path)

    git_dir = workspace_path / ".git"
    if not git_dir.exists():
        subprocess.run(
            ["git", "init"],
            cwd=str(workspace_path),
            capture_output=True,
            text=True,
            check=True,
        )
        gitignore = workspace_path / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text(
                "__pycache__/\n*.pyc\n.env\n.xdev/data/\n",
                encoding="utf-8",
            )
        subprocess.run(
            ["git", "add", "."],
            cwd=str(workspace_path),
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "init workspace", "--allow-empty"],
            cwd=str(workspace_path),
            capture_output=True,
            text=True,
        )

    (workspace_path / "tests").mkdir(exist_ok=True)
    (workspace_path / "docs").mkdir(exist_ok=True)


def get_workspace_status(workspace_path: Path | str) -> str:
    """Summarize workspace state for the supervisor prompt."""
    workspace_path = Path(workspace_path)

    xdev_dir = workspace_path / ".xdev"
    lines = []

    schema_path = xdev_dir / "schema.json"
    if schema_path.exists():
        try:
            data = json.loads(schema_path.read_text(encoding="utf-8"))
            schema_fields = list(data.get("data", {}).keys())
            fields_str = ", ".join(schema_fields) if schema_fields else "无字段"
            lines.append(f"schema: {len(schema_fields)} 个字段 ({fields_str})")
        except Exception:
            lines.append("schema: 存在但解析失败")
    else:
        lines.append("schema: 不存在")

    docjson_dir = xdev_dir / "data" / "docjson"
    doc_count = len(list(docjson_dir.glob("*.json"))) if docjson_dir.exists() else 0
    lines.append(f"文档数: {doc_count}")

    labels_dir = xdev_dir / "labels"
    label_count = len(list(labels_dir.glob("*.json"))) if labels_dir.exists() else 0
    if doc_count > 0:
        pct = label_count / doc_count * 100
        lines.append(f"已标注: {label_count}/{doc_count} ({pct:.0f}%)")
    else:
        lines.append(f"已标注: {label_count}")

    guide_path = workspace_path / "business_guide.md"
    if guide_path.exists():
        try:
            content = guide_path.read_text(encoding="utf-8")
            line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            char_count = len(content)
            lines.append(f"business_guide.md: 存在 ({line_count} 行, {char_count} 字)")
        except Exception:
            lines.append("business_guide.md: 存在（读取失败）")
    else:
        lines.append("business_guide.md: 不存在")

    program_path = workspace_path / "program.py"
    if program_path.exists():
        try:
            content = program_path.read_text(encoding="utf-8")
            line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            byte_count = program_path.stat().st_size
            lines.append(f"program.py: 存在 ({line_count} 行, {byte_count} 字节)")
        except Exception:
            lines.append("program.py: 存在（读取失败）")
    else:
        lines.append("program.py: 不存在")

    return "\n".join(lines)
