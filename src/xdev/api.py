"""
xdev 核心 API
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from .models import Manifest, Schema
from .config import get_data_dir, ensure_data_dir


@dataclass
class LabelIssue:
    """单个标注问题"""
    doc_id: str
    issue_type: str  # "missing_fields" | "extra_fields" | "type_error" | "structure_error"
    detail: str


@dataclass
class LabelStatusReport:
    """标注状态报告"""
    total_docs: int
    labeled_count: int
    unlabeled_ids: list[str]
    mismatched_ids: list[str]
    issues: list[LabelIssue] = field(default_factory=list)

    @property
    def unlabeled_count(self) -> int:
        return len(self.unlabeled_ids)

    @property
    def mismatched_count(self) -> int:
        return len(self.mismatched_ids)

    @property
    def needs_action_count(self) -> int:
        """需要处理的文档数（未标注 + 不匹配，去重）"""
        return len(set(self.unlabeled_ids) | set(self.mismatched_ids))

    @property
    def all_good(self) -> bool:
        return self.unlabeled_count == 0 and self.mismatched_count == 0


def get_manifest(data_dir: Path | str | None = None) -> Manifest | None:
    """读取 manifest.json

    Args:
        data_dir: 数据目录

    Returns:
        Manifest 对象，不存在则返回 None
    """
    path = get_data_dir(data_dir)
    manifest_file = path / "manifest.json"

    if not manifest_file.exists():
        return None

    with open(manifest_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    try:
        return Manifest(**data)
    except Exception:
        return None


def save_manifest(manifest: Manifest, data_dir: Path | str | None = None) -> None:
    """保存 manifest.json

    Args:
        manifest: Manifest 对象
        data_dir: 数据目录
    """
    path = ensure_data_dir(data_dir)
    manifest_file = path / "manifest.json"

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest.model_dump(), f, indent=2, ensure_ascii=False)


def get_schema(data_dir: Path | str | None = None) -> Schema | None:
    """读取 schema.json

    Args:
        data_dir: 数据目录

    Returns:
        Schema 对象，不存在则返回 None
    """
    path = get_data_dir(data_dir)
    schema_file = path / "schema.json"

    if not schema_file.exists():
        return None

    with open(schema_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        return Schema(**data)


def list_doc_ids(data_dir: Path | str | None = None) -> list[str]:
    """列出所有文档 ID

    Args:
        data_dir: 数据目录

    Returns:
        文档 ID 列表
    """
    path = get_data_dir(data_dir)
    docjson_dir = path / "data" / "docjson"

    if not docjson_dir.exists():
        return []

    doc_ids = []
    for file in docjson_dir.glob("*.json"):
        doc_ids.append(file.stem)

    return sorted(doc_ids)


def get_docjson_path(doc_id: str, data_dir: Path | str | None = None) -> Path:
    """获取 docjson 文件路径

    Args:
        doc_id: 文档 ID
        data_dir: 数据目录

    Returns:
        docjson 文件路径
    """
    path = get_data_dir(data_dir)
    return path / "data" / "docjson" / f"{doc_id}.json"


def get_pdf_path(doc_id: str, data_dir: Path | str | None = None) -> Path:
    """获取 PDF 文件路径

    Args:
        doc_id: 文档 ID
        data_dir: 数据目录

    Returns:
        PDF 文件路径
    """
    path = get_data_dir(data_dir)
    return path / "data" / "pdf" / f"{doc_id}.pdf"


def get_label_path(doc_id: str, data_dir: Path | str | None = None) -> Path:
    """获取标注文件路径

    Args:
        doc_id: 文档 ID
        data_dir: 数据目录

    Returns:
        标注文件路径
    """
    path = get_data_dir(data_dir)
    return path / "labels" / f"{doc_id}.json"


def get_label(doc_id: str, data_dir: Path | str | None = None) -> dict | list | None:
    """读取标注数据

    Args:
        doc_id: 文档 ID
        data_dir: 数据目录

    Returns:
        标注数据，不存在则返回 None
    """
    label_file = get_label_path(doc_id, data_dir)

    if not label_file.exists():
        return None

    with open(label_file, "r", encoding="utf-8") as f:
        return json.load(f)


def list_labeled_doc_ids(data_dir: Path | str | None = None) -> list[str]:
    """列出已标注的文档 ID

    Args:
        data_dir: 数据目录

    Returns:
        已标注的文档 ID 列表
    """
    path = get_data_dir(data_dir)
    labels_dir = path / "labels"

    if not labels_dir.exists():
        return []

    doc_ids = []
    for file in labels_dir.glob("*.json"):
        doc_ids.append(file.stem)

    return sorted(doc_ids)


_TYPE_CHECKERS: dict[str, tuple[type, ...]] = {
    "int": (int,),
    "float": (int, float),
    "bool": (bool,),
    "list": (list,),
}


def _check_object_against_schema(
    obj: dict,
    schema_keys: set[str],
    schema_data: dict[str, str],
    doc_id: str,
    issues: list[LabelIssue],
    prefix: str = "",
) -> bool:
    """检查单个对象的 key 一致性和类型，返回是否有问题"""
    has_issue = False
    obj_keys = set(obj.keys())

    missing = schema_keys - obj_keys
    extra = obj_keys - schema_keys

    if missing:
        issues.append(LabelIssue(
            doc_id=doc_id,
            issue_type="missing_fields",
            detail=f"{prefix}缺少字段 {sorted(missing)}",
        ))
        has_issue = True

    if extra:
        issues.append(LabelIssue(
            doc_id=doc_id,
            issue_type="extra_fields",
            detail=f"{prefix}多余字段 {sorted(extra)}",
        ))
        has_issue = True

    for key in schema_keys & obj_keys:
        value = obj[key]
        if value is None or value == "":
            continue

        expected_type = schema_data[key]
        if expected_type == "str":
            continue

        allowed = _TYPE_CHECKERS.get(expected_type)
        if allowed is None:
            continue

        if not isinstance(value, allowed):
            actual = type(value).__name__
            issues.append(LabelIssue(
                doc_id=doc_id,
                issue_type="type_error",
                detail=f"{prefix}字段类型错误 [{key}: 期望 {expected_type}, 实际 {actual}]",
            ))
            has_issue = True

    return has_issue


def add_documents(
    documents: list[tuple[Path, Path]],
    data_dir: Path | str | None = None,
    *,
    force: bool = False,
) -> list[str]:
    """增量添加文档（PDF + DocJSON 对）

    Args:
        documents: (pdf_path, docjson_path) 元组列表
        data_dir: 数据目录
        force: 是否覆盖已有文档

    Returns:
        成功添加的 doc_id 列表
    """
    import shutil

    target_dir = ensure_data_dir(data_dir)
    docjson_dst = target_dir / "data" / "docjson"
    pdf_dst = target_dir / "data" / "pdf"

    added_ids = []
    skipped = []

    for pdf_path, docjson_path in documents:
        pdf_path = Path(pdf_path)
        docjson_path = Path(docjson_path)

        if not pdf_path.exists() or not docjson_path.exists():
            continue

        doc_id = pdf_path.stem

        if (docjson_dst / f"{doc_id}.json").exists() and not force:
            skipped.append(doc_id)
            continue

        from .import_data import _write_canonical_docjson

        with open(docjson_path, "r", encoding="utf-8") as f:
            _write_canonical_docjson(docjson_dst / f"{doc_id}.json", json.load(f))
        shutil.copy2(pdf_path, pdf_dst / f"{doc_id}.pdf")
        added_ids.append(doc_id)

    if added_ids:
        from .import_data import _update_manifest_doc_count
        _update_manifest_doc_count(target_dir, data_dir)

    return added_ids


def check_label_status(data_dir: str | Path | None = None) -> LabelStatusReport:
    """检查标注状态，返回报告

    Args:
        data_dir: 数据目录

    Returns:
        LabelStatusReport

    Raises:
        FileNotFoundError: schema.json 不存在
    """
    schema = get_schema(data_dir)
    if schema is None:
        raise FileNotFoundError("schema.json 不存在，请先创建 schema")

    all_ids = list_doc_ids(data_dir)
    labeled_ids = set(list_labeled_doc_ids(data_dir))
    unlabeled_ids = [did for did in all_ids if did not in labeled_ids]

    schema_keys = set(schema.data.keys())
    issues: list[LabelIssue] = []
    mismatched_set: set[str] = set()

    for doc_id in sorted(labeled_ids):
        label = get_label(doc_id, data_dir)
        if label is None:
            continue

        doc_issues: list[LabelIssue] = []

        if schema.type == "object":
            if not isinstance(label, dict):
                doc_issues.append(LabelIssue(
                    doc_id=doc_id,
                    issue_type="structure_error",
                    detail=f"结构类型错误 [期望 dict, 实际 {type(label).__name__}]",
                ))
            else:
                _check_object_against_schema(label, schema_keys, schema.data, doc_id, doc_issues)

        elif schema.type == "list_of_objects":
            if not isinstance(label, list):
                doc_issues.append(LabelIssue(
                    doc_id=doc_id,
                    issue_type="structure_error",
                    detail=f"结构类型错误 [期望 list, 实际 {type(label).__name__}]",
                ))
            else:
                for i, item in enumerate(label):
                    if not isinstance(item, dict):
                        doc_issues.append(LabelIssue(
                            doc_id=doc_id,
                            issue_type="structure_error",
                            detail=f"元素 [{i}] 结构类型错误 [期望 dict, 实际 {type(item).__name__}]",
                        ))
                    else:
                        _check_object_against_schema(
                            item, schema_keys, schema.data, doc_id, doc_issues,
                            prefix=f"元素 [{i}] ",
                        )

        if doc_issues:
            mismatched_set.add(doc_id)
            issues.extend(doc_issues)

    return LabelStatusReport(
        total_docs=len(all_ids),
        labeled_count=len(labeled_ids),
        unlabeled_ids=unlabeled_ids,
        mismatched_ids=sorted(mismatched_set),
        issues=issues,
    )
