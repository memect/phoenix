"""Migrate legacy workspace formats (.cache/.extract-dev) to .xdev format."""

import json
import shutil
from datetime import datetime
from pathlib import Path


def migrate_legacy_workspace(workspace_path: Path | str) -> bool:
    """Migrate legacy .cache/.extract-dev workspace to .xdev format.

    Only migrates documents that have labels (from train.json or .extract-dev/labels.json).
    Test-only documents are excluded.

    Detects old workspace formats and converts them:
    - .extract-dev/schema.json → .xdev/schema.json (priority, already xdev format)
    - .cache/{set-id}/schema.json → .xdev/schema.json (fallback, auto-wraps flat format)
    - .extract-dev/labels.json → .xdev/labels/{doc_id}.json (priority)
    - .cache/{set-id}/standard_for_evaluate/train.json → .xdev/labels/ (fallback)
    - .cache/{set-id}/docjson/ → .xdev/data/docjson/ (only labeled docs)
    - .cache/{set-id}/pdf/ → .xdev/data/pdf/ (only labeled docs)

    Args:
        workspace_path: Path to workspace root

    Returns:
        True if migration was performed, False if not needed
    """
    workspace_path = Path(workspace_path)
    xdev_dir = workspace_path / ".xdev"

    if (xdev_dir / "manifest.json").exists():
        return False

    cache_dir = workspace_path / ".cache"
    if not cache_dir.exists():
        return False

    # Find set-id subdirectory (first one with docjson/)
    set_id_dir = None
    set_id = None
    for child in cache_dir.iterdir():
        if child.is_dir() and (child / "docjson").exists():
            set_id_dir = child
            set_id = child.name
            break

    if set_id_dir is None:
        print("[migrate] .cache/ 存在但未找到有效的数据目录，跳过迁移")
        return False

    print(f"[migrate] 检测到旧格式 workspace，开始迁移 (set_id={set_id})")

    # Collect labeled doc_ids first (file-name format, no dashes)
    doc_ids = _collect_label_doc_ids(workspace_path, set_id_dir)
    if not doc_ids:
        print("[migrate] 未找到标注数据，跳过迁移")
        return False

    print(f"[migrate] 找到 {len(doc_ids)} 个有标注的文档")

    # Create .xdev structure
    data_docjson = xdev_dir / "data" / "docjson"
    data_pdf = xdev_dir / "data" / "pdf"
    labels_dir = xdev_dir / "labels"
    data_docjson.mkdir(parents=True, exist_ok=True)
    data_pdf.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    # Copy docjson files (only labeled docs)
    src_docjson = set_id_dir / "docjson"
    if src_docjson.exists():
        count = 0
        for f in src_docjson.glob("*.json"):
            if f.stem in doc_ids:
                shutil.copy2(f, data_docjson / f.name)
                count += 1
        print(f"[migrate] 复制 {count} 个 docjson 文件")

    # Copy pdf files (only labeled docs)
    src_pdf = set_id_dir / "pdf"
    if src_pdf.exists():
        count = 0
        for f in src_pdf.glob("*.pdf"):
            if f.stem in doc_ids:
                shutil.copy2(f, data_pdf / f.name)
                count += 1
        print(f"[migrate] 复制 {count} 个 PDF 文件")

    # Migrate schema
    _migrate_schema(workspace_path, set_id_dir, xdev_dir)

    # Migrate labels
    _migrate_labels(workspace_path, set_id_dir, labels_dir)

    # Generate manifest.json
    doc_count = len(list(data_docjson.glob("*.json")))
    manifest_data = {
        "source": {
            "type": "data-dir",
            "path": str(xdev_dir / "data"),
        },
        "imported_at": datetime.now().isoformat(),
        "doc_count": doc_count,
        "migration_info": {
            "original_set_id": set_id,
            "migrated_at": datetime.now().isoformat(),
        },
    }
    manifest_path = xdev_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    label_count = len(list(labels_dir.glob("*.json")))
    print(f"[migrate] 迁移完成: {doc_count} 个文档, {label_count} 个标注")
    return True


def _collect_label_doc_ids(
    workspace_path: Path, set_id_dir: Path
) -> set[str]:
    """Collect doc_ids that have labels, in file-name format (no dashes).

    Labels sources use UUID with dashes (e.g. 716d80da-4c92-3a17-03af-c8fd0a54d41f),
    but docjson/pdf file names use UUID without dashes (e.g. 716d80da4c923a1703afc8fd0a54d41f).
    This function returns doc_ids in file-name format (no dashes).

    Priority:
    1. .extract-dev/labels.json
    2. .cache/{set-id}/standard_for_evaluate/train.json

    Args:
        workspace_path: Workspace root
        set_id_dir: .cache/{set-id}/ directory

    Returns:
        Set of doc_ids in file-name format (no dashes)
    """
    # Priority 1: .extract-dev/labels.json
    extract_dev_labels = workspace_path / ".extract-dev" / "labels.json"
    if extract_dev_labels.exists():
        try:
            labels_list = json.loads(
                extract_dev_labels.read_text(encoding="utf-8")
            )
            doc_ids = set()
            for item in labels_list:
                doc_id = item.get("id")
                if doc_id and item.get("labels") is not None:
                    doc_ids.add(doc_id.replace("-", ""))
            if doc_ids:
                return doc_ids
        except Exception as e:
            print(f"[migrate] 读取 .extract-dev/labels.json 失败: {e}")

    # Priority 2: train.json
    train_json = set_id_dir / "standard_for_evaluate" / "train.json"
    if train_json.exists():
        try:
            train_list = json.loads(train_json.read_text(encoding="utf-8"))
            doc_ids = set()
            for item in train_list:
                doc_id = item.get("id") or item.get("document_id")
                if doc_id and item.get("labels") is not None:
                    doc_ids.add(doc_id.replace("-", ""))
            if doc_ids:
                return doc_ids
        except Exception as e:
            print(f"[migrate] 读取 train.json 失败: {e}")

    return set()


def _migrate_schema(
    workspace_path: Path, set_id_dir: Path, xdev_dir: Path
) -> bool:
    """Migrate schema to .xdev/schema.json.

    Priority:
    1. .extract-dev/schema.json (already in xdev format: {type, data})
    2. .cache/{set-id}/schema.json (old flat format: {field: type}, needs wrapping)

    Args:
        workspace_path: Workspace root
        set_id_dir: .cache/{set-id}/ directory
        xdev_dir: Target .xdev/ directory

    Returns:
        True if schema was migrated
    """
    dest = xdev_dir / "schema.json"

    # Priority 1: .extract-dev/schema.json (already xdev format)
    extract_dev_schema = workspace_path / ".extract-dev" / "schema.json"
    if extract_dev_schema.exists():
        try:
            data = json.loads(extract_dev_schema.read_text(encoding="utf-8"))
            if "type" in data and "data" in data:
                # Already in xdev format
                shutil.copy2(extract_dev_schema, dest)
                print("[migrate] 复制 .extract-dev/schema.json")
                return True
        except Exception as e:
            print(f"[migrate] 读取 .extract-dev/schema.json 失败: {e}")

    # Priority 2: .cache/{set-id}/schema.json (may be old flat format)
    cache_schema = set_id_dir / "schema.json"
    if cache_schema.exists():
        try:
            data = json.loads(cache_schema.read_text(encoding="utf-8"))
            if "type" in data and "data" in data:
                # Already in xdev format
                shutil.copy2(cache_schema, dest)
                print("[migrate] 复制 schema.json")
            else:
                # Old flat format {field: type} → wrap as {type: "object", data: {...}}
                wrapped = {"type": "object", "data": data}
                dest.write_text(
                    json.dumps(wrapped, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                print("[migrate] 转换 schema.json (flat → xdev 格式)")
            return True
        except Exception as e:
            print(f"[migrate] 读取 .cache schema.json 失败: {e}")

    print("[migrate] 未找到 schema")
    return False


def _migrate_labels(
    workspace_path: Path, set_id_dir: Path, labels_dir: Path
) -> int:
    """Migrate labels from legacy format to .xdev/labels/{doc_id}.json.

    Priority:
    1. .extract-dev/labels.json (complete replacement semantics)
    2. .cache/{set-id}/standard_for_evaluate/train.json (fallback)

    Args:
        workspace_path: Workspace root
        set_id_dir: .cache/{set-id}/ directory
        labels_dir: Target .xdev/labels/ directory

    Returns:
        Number of label files created
    """
    count = 0

    # Priority 1: .extract-dev/labels.json
    extract_dev_labels = workspace_path / ".extract-dev" / "labels.json"
    if extract_dev_labels.exists():
        try:
            labels_list = json.loads(
                extract_dev_labels.read_text(encoding="utf-8")
            )
            for item in labels_list:
                doc_id = item.get("id")
                labels = item.get("labels")
                if doc_id and labels is not None:
                    # Use no-dash format to match docjson file names
                    file_id = doc_id.replace("-", "")
                    label_path = labels_dir / f"{file_id}.json"
                    label_path.write_text(
                        json.dumps(labels, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    count += 1
            print(f"[migrate] 从 .extract-dev/labels.json 迁移 {count} 个标注")
            return count
        except Exception as e:
            print(f"[migrate] 读取 .extract-dev/labels.json 失败: {e}")

    # Priority 2: standard_for_evaluate/train.json
    train_json = set_id_dir / "standard_for_evaluate" / "train.json"
    if train_json.exists():
        try:
            train_list = json.loads(train_json.read_text(encoding="utf-8"))
            for item in train_list:
                doc_id = item.get("id") or item.get("document_id")
                labels = item.get("labels")
                if doc_id and labels is not None:
                    # Use no-dash format to match docjson file names
                    file_id = doc_id.replace("-", "")
                    label_path = labels_dir / f"{file_id}.json"
                    label_path.write_text(
                        json.dumps(labels, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    count += 1
            print(
                f"[migrate] 从 standard_for_evaluate/train.json 迁移 {count} 个标注"
            )
            return count
        except Exception as e:
            print(f"[migrate] 读取 train.json 失败: {e}")

    print("[migrate] 未找到标注数据")
    return 0
