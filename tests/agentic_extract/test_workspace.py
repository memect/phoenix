import json

import pytest

from agentic_extract.workspace import (
    ensure_workspace_ready,
    get_workspace_status,
    init_workspace,
    normalize_workspace_data,
    workspace_has_runnable_data,
)


def test_init_workspace_creates_basic_layout(tmp_path):
    init_workspace(tmp_path)

    assert (tmp_path / "tests").exists()
    assert (tmp_path / "docs").exists()
    assert (tmp_path / ".gitignore").exists()
    assert not (tmp_path / "docs" / "data_issues.md").exists()
    assert not (tmp_path / "docs" / "known_limitations.md").exists()
    assert not (tmp_path / "docs" / "notes.md").exists()


def test_get_workspace_status_summarizes_known_files(tmp_path):
    xdev_dir = tmp_path / ".xdev"
    (xdev_dir / "data" / "docjson").mkdir(parents=True)
    (xdev_dir / "labels").mkdir(parents=True)
    (xdev_dir / "schema.json").write_text(
        json.dumps({"data": {"field_a": {}, "field_b": {}}}),
        encoding="utf-8",
    )
    (xdev_dir / "data" / "docjson" / "doc1.json").write_text("{}", encoding="utf-8")
    (xdev_dir / "labels" / "doc1.json").write_text("{}", encoding="utf-8")
    (tmp_path / "business_guide.md").write_text("hello\nworld\n", encoding="utf-8")
    (tmp_path / "program.py").write_text("print('ok')\n", encoding="utf-8")

    status = get_workspace_status(tmp_path)

    assert "schema: 2 个字段" in status
    assert "文档数: 1" in status
    assert "已标注: 1/1 (100%)" in status
    assert "business_guide.md: 存在" in status
    assert "program.py: 存在" in status


def test_normalize_workspace_data_generates_manifest_from_existing_docjson(tmp_path):
    docjson_dir = tmp_path / ".xdev" / "data" / "docjson"
    docjson_dir.mkdir(parents=True)
    (docjson_dir / "doc1.json").write_text("{}", encoding="utf-8")

    normalize_workspace_data(tmp_path)

    assert (tmp_path / ".xdev" / "manifest.json").exists()
    assert workspace_has_runnable_data(tmp_path) is True


def test_ensure_workspace_ready_raises_when_no_runnable_data(tmp_path):
    with pytest.raises(ValueError, match="缺少可运行的 .xdev 数据"):
        ensure_workspace_ready(tmp_path)


def test_ensure_workspace_ready_can_skip_normalize_for_dry_run(tmp_path):
    docjson_dir = tmp_path / ".xdev" / "data" / "docjson"
    docjson_dir.mkdir(parents=True)
    (docjson_dir / "doc1.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="缺少可运行的 .xdev 数据"):
        ensure_workspace_ready(tmp_path, allow_normalize=False)

    assert not (tmp_path / ".xdev" / "manifest.json").exists()
