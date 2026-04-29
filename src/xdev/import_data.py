"""
xdev 数据导入功能
"""

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from .models import Manifest, DataSourceSetId, DataSourcePdfs, DataSourceDataDir, DataSource
from .config import ensure_data_dir, load_config


def _write_canonical_docjson(path: Path, docjson: dict) -> None:
    from code_executor.document.docjson_adapter import normalize_docjson

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(normalize_docjson(docjson), f, ensure_ascii=False, indent=2)


@dataclass
class SyncResult:
    """同步结果"""
    added: list[str]
    removed: list[str]
    modified: list[str]
    unchanged: list[str]

    @property
    def total_changes(self) -> int:
        return len(self.added) + len(self.removed) + len(self.modified)


def parse_std_ids_file(path: str | Path) -> list[str]:
    """从文件读取文档 ID 白名单（一行一个 ID，空行和 # 开头的行忽略）"""
    ids = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                ids.append(line)
    return ids


def resolve_std_ids(
    std_ids: str | None = None,
    std_ids_file: str | None = None,
) -> list[str] | None:
    """从 CLI 参数解析文档 ID 白名单

    Args:
        std_ids: 逗号分隔的 ID 字符串
        std_ids_file: ID 文件路径

    Returns:
        合并后的 ID 列表，如果都为空则返回 None
    """
    result: list[str] = []
    if std_ids:
        result.extend(s.strip() for s in std_ids.split(",") if s.strip())
    if std_ids_file:
        result.extend(parse_std_ids_file(std_ids_file))
    return result if result else None


def import_from_set_id(
    set_id: str,
    base_url: str,
    data_dir: Path | str | None = None,
    std_ids: list[str] | None = None,
    sync: bool = False,
    skip_exist: bool = False,
    limit: int | None = None,
) -> None:
    """从远程标准集导入数据

    Args:
        set_id: 标准集 ID
        base_url: API 地址
        data_dir: 数据目录
        std_ids: 可选的文档 ID 白名单，仅导入这些文档
        sync: 同步模式，导入后删除远程不存在的本地文档
        skip_exist: 跳过本地已有的文档，不重新下载
        limit: 限制导入文档数量
    """
    from evaluation_engine.api import download_dataset

    print("正在从远程标准集下载数据...")
    print(f"  set_id: {set_id}")
    print(f"  base_url: {base_url}")
    if std_ids:
        print(f"  白名单: {len(std_ids)} 个文档")
    if limit is not None:
        print(f"  限制: {limit} 个文档")
    if sync:
        print("  模式: sync（删除远程不存在的本地文档）")
    if skip_exist:
        print("  模式: skip-exist（跳过已有文档）")

    # 下载到临时目录
    cache_dir = Path.home() / ".cache" / "xdev" / set_id
    cache_dir.mkdir(parents=True, exist_ok=True)

    download_kwargs: dict = dict(download_pdf=True, std_ids=std_ids)
    if limit is not None:
        download_kwargs["max_size"] = limit

    data_path = download_dataset(set_id, base_url, str(cache_dir), **download_kwargs)
    print(f"  下载完成: {data_path}")

    # 复制到目标目录
    target_dir = ensure_data_dir(data_dir)
    source_data_dir = Path(data_path)

    # 收集远程文档 ID（用于 sync 模式）
    remote_doc_ids: set[str] = set()

    # 复制 docjson
    docjson_src = source_data_dir / "docjson"
    docjson_dst = target_dir / "data" / "docjson"
    copied_count = 0
    skipped_count = 0
    if docjson_src.exists():
        for file in docjson_src.glob("*.json"):
            remote_doc_ids.add(file.stem)
            if skip_exist and (docjson_dst / file.name).exists():
                skipped_count += 1
                continue
            with open(file, "r", encoding="utf-8") as f:
                _write_canonical_docjson(docjson_dst / file.name, json.load(f))
            copied_count += 1
        print(f"  已复制 docjson: {copied_count} 个文件" + (f"（跳过 {skipped_count} 个已有）" if skipped_count else ""))

    # 复制 pdf
    pdf_src = source_data_dir / "pdf"
    pdf_dst = target_dir / "data" / "pdf"
    if pdf_src.exists():
        pdf_copied = 0
        pdf_skipped = 0
        for file in pdf_src.glob("*.pdf"):
            if skip_exist and (pdf_dst / file.name).exists():
                pdf_skipped += 1
                continue
            shutil.copy2(file, pdf_dst / file.name)
            pdf_copied += 1
        print(f"  已复制 pdf: {pdf_copied} 个文件" + (f"（跳过 {pdf_skipped} 个已有）" if pdf_skipped else ""))

    # 复制 schema
    schema_src = source_data_dir / "schema.json"
    schema_dst = target_dir / "schema.json"
    if schema_src.exists():
        shutil.copy2(schema_src, schema_dst)
        print("  已复制 schema.json")

    # 导入标注数据（从 train.json / test.json 中提取 labels）
    labels_dst = target_dir / "labels"
    std_eval_dir = source_data_dir / "standard_for_evaluate"
    label_count = 0
    if std_eval_dir.exists():
        import uuid as _uuid
        for filename in ["train.json", "test.json"]:
            std_file = std_eval_dir / filename
            if not std_file.exists():
                continue
            with open(std_file, "r", encoding="utf-8") as f:
                entries = json.load(f)
            for entry in entries:
                doc_id = entry.get("document_id")
                labels = entry.get("labels")
                if doc_id is None or labels is None:
                    continue
                hex_id = _uuid.UUID(doc_id).hex
                label_path = labels_dst / f"{hex_id}.json"
                with open(label_path, "w", encoding="utf-8") as f:
                    json.dump(labels, f, ensure_ascii=False, indent=2)
                label_count += 1
        if label_count:
            print(f"  已导入标注: {label_count} 个文件")

    # sync 模式：删除远程不存在的本地文档
    removed_count = 0
    if sync and remote_doc_ids:
        local_doc_ids = {f.stem for f in docjson_dst.glob("*.json")}
        to_remove = local_doc_ids - remote_doc_ids
        for doc_id in to_remove:
            (docjson_dst / f"{doc_id}.json").unlink(missing_ok=True)
            (pdf_dst / f"{doc_id}.pdf").unlink(missing_ok=True)
            removed_count += 1
        if removed_count:
            print(f"  已删除本地多余文档: {removed_count} 个")

    # 保存 manifest（含 std_ids）
    doc_count = len(list(docjson_dst.glob("*.json")))
    manifest = Manifest(
        source=DataSourceSetId(set_id=set_id, base_url=base_url, std_ids=std_ids),
        imported_at=datetime.now().isoformat(),
        doc_count=doc_count,
    )

    from .api import save_manifest
    save_manifest(manifest, data_dir)

    print("\n导入完成！")
    print(f"  数据目录: {target_dir}")
    print(f"  文档数量: {doc_count}")
    if label_count:
        print(f"  标注数量: {label_count}")
    if removed_count:
        print(f"  删除数量: {removed_count}")


def import_from_pdfs(pdf_dir: str, data_dir: Path | str | None = None) -> None:
    """从本地 PDF 目录导入数据（调用 PPX 解析 PDF → DocJSON）

    Args:
        pdf_dir: PDF 目录路径
        data_dir: 数据目录
    """
    from code_executor.document.utils.pdf_parser import parse_pdf_dir_to_docjsons

    pdf_path = Path(pdf_dir)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 目录不存在: {pdf_dir}")

    pdf_files = sorted(pdf_path.glob("*.pdf"))
    if not pdf_files:
        raise ValueError(f"PDF 目录为空: {pdf_dir}")

    print("正在从本地 PDF 目录导入数据...")
    print(f"  PDF 目录: {pdf_dir}")
    print(f"  PDF 数量: {len(pdf_files)}")

    target_dir = ensure_data_dir(data_dir)
    config = load_config()
    print(f"  PPX PDF 并发: {config.pdf_parse_concurrent}")

    docjsons = parse_pdf_dir_to_docjsons(
        pdf_path,
        workers=config.pdf_parse_concurrent,
    )
    results = [(pdf_file.stem, docjsons[pdf_file.stem]) for pdf_file in pdf_files]
    for i, (doc_id, _) in enumerate(results, 1):
        print(f"  [{i}/{len(pdf_files)}] 已解析: {doc_id}")

    # 保存结果
    docjson_dst = target_dir / "data" / "docjson"
    pdf_dst = target_dir / "data" / "pdf"

    for doc_id, docjson in results:
        # 保存 docjson
        _write_canonical_docjson(docjson_dst / f"{doc_id}.json", docjson)

        # 复制 PDF
        src_pdf = pdf_path / f"{doc_id}.pdf"
        if src_pdf.exists():
            shutil.copy2(src_pdf, pdf_dst / f"{doc_id}.pdf")

    # 保存 manifest
    manifest = Manifest(
        source=DataSourcePdfs(pdf_dir=str(pdf_path.absolute())),
        imported_at=datetime.now().isoformat(),
        doc_count=len(results),
    )

    from .api import save_manifest
    save_manifest(manifest, data_dir)

    print("\n导入完成！")
    print(f"  数据目录: {target_dir}")
    print(f"  文档数量: {len(results)}")


def import_from_data_dir(source_dir: str, data_dir: Path | str | None = None) -> None:
    """从另一个 data-dir 导入数据

    Args:
        source_dir: 源数据目录
        data_dir: 目标数据目录
    """
    source_path = Path(source_dir)
    if not source_path.exists():
        raise FileNotFoundError(f"源数据目录不存在: {source_dir}")

    print("正在从数据目录导入...")
    print(f"  源目录: {source_dir}")

    target_dir = ensure_data_dir(data_dir)

    # 复制 data/
    source_data = source_path / "data"
    if source_data.exists():
        for subdir in ["docjson", "pdf"]:
            src = source_data / subdir
            dst = target_dir / "data" / subdir
            if src.exists():
                for file in src.iterdir():
                    if subdir == "docjson" and file.suffix == ".json":
                        with open(file, "r", encoding="utf-8") as f:
                            _write_canonical_docjson(dst / file.name, json.load(f))
                    else:
                        shutil.copy2(file, dst / file.name)
                print(f"  已复制 {subdir}: {len(list(dst.iterdir()))} 个文件")

    # 复制 schema.json
    schema_src = source_path / "schema.json"
    schema_dst = target_dir / "schema.json"
    if schema_src.exists():
        shutil.copy2(schema_src, schema_dst)
        print("  已复制 schema.json")

    # 复制 labels/
    labels_src = source_path / "labels"
    labels_dst = target_dir / "labels"
    if labels_src.exists():
        for file in labels_src.glob("*.json"):
            shutil.copy2(file, labels_dst / file.name)
        print(f"  已复制标注: {len(list(labels_dst.glob('*.json')))} 个文件")

    # 保存 manifest
    doc_count = len(list((target_dir / "data" / "docjson").glob("*.json")))
    manifest = Manifest(
        source=DataSourceDataDir(path=str(source_path.absolute())),
        imported_at=datetime.now().isoformat(),
        doc_count=doc_count,
    )

    from .api import save_manifest
    save_manifest(manifest, data_dir)

    print("\n导入完成！")
    print(f"  数据目录: {target_dir}")
    print(f"  文档数量: {doc_count}")


def import_from_source(source_file: str, data_dir: Path | str | None = None) -> None:
    """从数据源配置文件导入

    Args:
        source_file: 数据源配置文件路径
        data_dir: 数据目录
    """
    with open(source_file, "r", encoding="utf-8") as f:
        source_data = json.load(f)

    source = DataSource.model_validate(source_data)

    if isinstance(source, DataSourceSetId):
        import_from_set_id(source.set_id, source.base_url, data_dir, std_ids=source.std_ids)
    elif isinstance(source, DataSourcePdfs):
        import_from_pdfs(source.pdf_dir, data_dir)
    elif isinstance(source, DataSourceDataDir):
        import_from_data_dir(source.path, data_dir)
    else:
        raise ValueError(f"未知的数据源类型: {source.type}")


# ---------------------------------------------------------------------------
# 增量操作
# ---------------------------------------------------------------------------

def add_pdfs(
    pdf_path: str | Path,
    data_dir: Path | str | None = None,
    *,
    force: bool = False,
) -> list[str]:
    """增量添加 PDF 文档

    Args:
        pdf_path: 单个 PDF 文件或包含 PDF 的目录
        data_dir: 数据目录
        force: 是否覆盖已有文档

    Returns:
        成功添加的 doc_id 列表
    """
    from code_executor.document.utils.pdf_parser import (
        parse_pdf_file_to_docjson,
        parse_pdf_files_to_docjsons,
    )

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"路径不存在: {pdf_path}")

    if pdf_path.is_file():
        if not pdf_path.name.endswith(".pdf"):
            raise ValueError(f"不是 PDF 文件: {pdf_path}")
        pdf_files = [pdf_path]
    else:
        pdf_files = sorted(pdf_path.glob("*.pdf"))
        if not pdf_files:
            raise ValueError(f"目录中没有 PDF 文件: {pdf_path}")

    target_dir = ensure_data_dir(data_dir)
    docjson_dst = target_dir / "data" / "docjson"
    pdf_dst = target_dir / "data" / "pdf"
    config = load_config()

    # 过滤已存在的文档
    to_process = []
    skipped = []
    for f in pdf_files:
        doc_id = f.stem
        if (docjson_dst / f"{doc_id}.json").exists() and not force:
            skipped.append(doc_id)
        else:
            to_process.append(f)

    if skipped:
        print(f"跳过已存在的文档 ({len(skipped)} 个): {', '.join(skipped[:5])}"
              + ("..." if len(skipped) > 5 else ""))
        print("  使用 --force 覆盖已有文档")

    if not to_process:
        print("没有需要添加的 PDF")
        return []

    print("正在添加 PDF 文档...")
    print(f"  待处理: {len(to_process)} 个")

    added_ids = []
    if len(to_process) == 1 and pdf_path.is_file():
        src_file = to_process[0]
        doc_id = src_file.stem
        docjson = parse_pdf_file_to_docjson(str(src_file))
        _write_canonical_docjson(docjson_dst / f"{doc_id}.json", docjson)
        shutil.copy2(src_file, pdf_dst / f"{doc_id}.pdf")
        added_ids.append(doc_id)
        print(f"  [1/1] 已添加: {doc_id}")
    else:
        print(f"  PPX PDF 并发: {config.pdf_parse_concurrent}")
        docjsons = parse_pdf_files_to_docjsons(
            to_process,
            workers=config.pdf_parse_concurrent,
        )
        for i, src_file in enumerate(to_process, 1):
            doc_id = src_file.stem
            docjson = docjsons[doc_id]
            _write_canonical_docjson(docjson_dst / f"{doc_id}.json", docjson)
            shutil.copy2(src_file, pdf_dst / f"{doc_id}.pdf")
            added_ids.append(doc_id)
            print(f"  [{i}/{len(to_process)}] 已添加: {doc_id}")

    _update_manifest_doc_count(target_dir, data_dir)
    print(f"\n添加完成！成功 {len(added_ids)} 个")
    return added_ids


def reparse_docs(
    doc_ids: list[str] | None = None,
    data_dir: Path | str | None = None,
) -> list[str]:
    """重新解析已有 PDF 生成新 DocJSON

    Args:
        doc_ids: 指定文档 ID 列表，None 则全部
        data_dir: 数据目录

    Returns:
        成功重新解析的 doc_id 列表
    """
    from code_executor.document.utils.pdf_parser import parse_pdf_files_to_docjsons

    target_dir = ensure_data_dir(data_dir)
    pdf_dir = target_dir / "data" / "pdf"
    docjson_dir = target_dir / "data" / "docjson"
    config = load_config()

    if doc_ids is None:
        pdf_files = sorted(pdf_dir.glob("*.pdf"))
    else:
        pdf_files = []
        for doc_id in doc_ids:
            p = pdf_dir / f"{doc_id}.pdf"
            if p.exists():
                pdf_files.append(p)
            else:
                print(f"  警告: PDF 不存在，跳过: {doc_id}")

    if not pdf_files:
        print("没有需要重新解析的 PDF")
        return []

    print("正在重新解析 PDF...")
    print(f"  待处理: {len(pdf_files)} 个")
    print(f"  PPX PDF 并发: {config.pdf_parse_concurrent}")

    reparsed_ids = []
    docjsons = parse_pdf_files_to_docjsons(
        pdf_files,
        workers=config.pdf_parse_concurrent,
    )
    for i, pdf_file in enumerate(pdf_files, 1):
        doc_id = pdf_file.stem
        docjson = docjsons[doc_id]
        _write_canonical_docjson(docjson_dir / f"{doc_id}.json", docjson)
        reparsed_ids.append(doc_id)
        print(f"  [{i}/{len(pdf_files)}] 已解析: {doc_id}")

    print(f"\n重新解析完成！成功 {len(reparsed_ids)} 个")
    return reparsed_ids


def _update_manifest_doc_count(target_dir: Path, data_dir: Path | str | None) -> None:
    """更新 manifest 中的 doc_count"""
    from .api import get_manifest, save_manifest

    manifest = get_manifest(data_dir)
    if manifest is None:
        return

    doc_count = len(list((target_dir / "data" / "docjson").glob("*.json")))
    manifest.doc_count = doc_count
    save_manifest(manifest, data_dir)


# ---------------------------------------------------------------------------
# 符号链接检查与修复
# ---------------------------------------------------------------------------

def check_symlinks(data_dir: Path | str | None = None) -> list[Path]:
    """检查数据目录中的符号链接

    Returns:
        符号链接路径列表
    """
    from .config import get_data_dir

    target_dir = get_data_dir(data_dir)
    if not target_dir.exists():
        return []

    symlinks = []
    for subdir in ["data/docjson", "data/pdf", "labels"]:
        d = target_dir / subdir
        if not d.exists():
            continue
        for f in d.iterdir():
            if f.is_symlink():
                symlinks.append(f)

    return symlinks


def fix_symlinks(data_dir: Path | str | None = None) -> list[Path]:
    """修复数据目录中的符号链接（替换为真实文件副本）

    Returns:
        已修复的路径列表
    """
    symlinks = check_symlinks(data_dir)
    fixed = []
    for link_path in symlinks:
        real_path = link_path.resolve()
        if not real_path.exists():
            print(f"  警告: 符号链接目标不存在，跳过: {link_path} -> {real_path}")
            continue
        link_path.unlink()
        shutil.copy2(real_path, link_path)
        fixed.append(link_path)

    return fixed


def warn_symlinks(data_dir: Path | str | None = None) -> bool:
    """检查并警告数据目录中的符号链接

    Returns:
        True 如果存在符号链接
    """
    symlinks = check_symlinks(data_dir)
    if symlinks:
        print(f"⚠ 数据目录中存在 {len(symlinks)} 个符号链接：")
        for s in symlinks[:5]:
            print(f"  {s} -> {s.resolve()}")
        if len(symlinks) > 5:
            print(f"  ... 还有 {len(symlinks) - 5} 个")
        print("  运行 `xdev fix-symlinks --fix` 修复")
        return True
    return False


# ---------------------------------------------------------------------------
# PDF 同步
# ---------------------------------------------------------------------------

def _compute_pdf_hash(pdf_path: Path) -> str:
    """计算 PDF 文件的 MD5 hash"""
    md5 = hashlib.md5()
    with open(pdf_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def _parse_and_save_pdfs(
    pdf_list: list[tuple[str, Path]],
    data_dir: Path,
) -> None:
    """调用 PPX 批量解析 PDF 并保存"""
    from code_executor.document.utils.pdf_parser import parse_pdf_files_to_docjsons

    config = load_config()

    docjson_dir = data_dir / "data" / "docjson"
    pdf_dst_dir = data_dir / "data" / "pdf"

    pdf_files = [pdf_path for _, pdf_path in pdf_list]
    print(f"[sync-pdfs] PPX PDF 并发: {config.pdf_parse_concurrent}")
    docjsons = parse_pdf_files_to_docjsons(
        pdf_files,
        workers=config.pdf_parse_concurrent,
    )

    success_count = 0
    for doc_id, pdf_path in pdf_list:
        docjson = docjsons[pdf_path.stem]
        docjson_path = docjson_dir / f"{doc_id}.json"
        _write_canonical_docjson(docjson_path, docjson)
        pdf_dst = pdf_dst_dir / f"{doc_id}.pdf"
        shutil.copy2(pdf_path, pdf_dst)
        success_count += 1

    print(f"[sync-pdfs] 解析完成: {success_count}/{len(pdf_list)}")


def sync_pdfs(
    pdf_dir: str | Path,
    data_dir: Path | str | None = None,
) -> SyncResult:
    """同步 PDF 目录到 .xdev/data/

    对比源 PDF 目录与已有数据，自动处理新增/删除/修改。
    删除时保留 label 文件。

    Args:
        pdf_dir: 源 PDF 目录路径
        data_dir: 数据目录

    Returns:
        SyncResult 同步结果

    Raises:
        FileNotFoundError: manifest 或 PDF 目录不存在
        ValueError: 数据源类型不匹配或 PDF 目录为空
    """
    from .api import get_manifest, save_manifest
    from .config import get_data_dir

    manifest = get_manifest(data_dir)
    if manifest is None:
        raise FileNotFoundError("manifest.json 不存在，请先运行 xdev import-data")

    if manifest.source.type != "pdfs":
        raise ValueError(f"数据源类型为 {manifest.source.type}，不支持同步")

    pdf_dir = Path(pdf_dir)
    if not pdf_dir.exists():
        raise FileNotFoundError(f"PDF 目录不存在: {pdf_dir}")

    source_pdfs = list(pdf_dir.glob("*.pdf"))
    if not source_pdfs:
        raise ValueError(f"PDF 目录为空: {pdf_dir}")

    target_dir = get_data_dir(data_dir)
    docjson_dir = target_dir / "data" / "docjson"
    pdf_data_dir = target_dir / "data" / "pdf"

    source_pdf_map = {p.stem: p for p in source_pdfs}
    target_doc_ids = {p.stem for p in docjson_dir.glob("*.json")} if docjson_dir.exists() else set()

    added = []
    removed = []
    modified = []
    unchanged = []

    for doc_id, src_path in source_pdf_map.items():
        if doc_id not in target_doc_ids:
            added.append(doc_id)
        else:
            target_pdf = pdf_data_dir / f"{doc_id}.pdf"
            if target_pdf.exists():
                source_hash = _compute_pdf_hash(src_path)
                target_hash = _compute_pdf_hash(target_pdf)
                if source_hash != target_hash:
                    modified.append(doc_id)
                else:
                    unchanged.append(doc_id)
            else:
                modified.append(doc_id)

    for doc_id in target_doc_ids:
        if doc_id not in source_pdf_map:
            removed.append(doc_id)

    to_parse = [(doc_id, source_pdf_map[doc_id]) for doc_id in added + modified]
    if to_parse:
        print(f"[sync-pdfs] 解析 {len(to_parse)} 篇 PDF...")
        _parse_and_save_pdfs(to_parse, target_dir)

    if removed:
        print(f"[sync-pdfs] 删除 {len(removed)} 篇过期文档...")
        for doc_id in removed:
            (docjson_dir / f"{doc_id}.json").unlink(missing_ok=True)
            (pdf_data_dir / f"{doc_id}.pdf").unlink(missing_ok=True)

    manifest.source = DataSourcePdfs(pdf_dir=str(pdf_dir.resolve()))
    manifest.doc_count = len(source_pdf_map)
    manifest.imported_at = datetime.now().isoformat()
    save_manifest(manifest, data_dir)

    return SyncResult(
        added=added,
        removed=removed,
        modified=modified,
        unchanged=unchanged,
    )
