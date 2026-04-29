"""Workspace data preparation helpers for high-level auto entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from xdev.api import get_manifest
from xdev.import_data import (
    import_from_data_dir,
    import_from_pdfs,
    import_from_set_id,
    import_from_source,
)
from xdev.models import DataSourceDataDir, DataSourcePdfs, DataSourceSetId

from .types import (
    PrepareSourceConfigFile,
    PrepareSourceDataDir,
    PrepareSourceExisting,
    PrepareSourcePdfDir,
    PrepareSourceSetId,
    PrepareSpec,
)
from .workspace import ensure_workspace_ready, workspace_has_runnable_data


@dataclass(frozen=True)
class PrepareDecision:
    action: str
    reason: str


def resolve_prepare_spec(prepare: PrepareSpec | None) -> PrepareSpec:
    return prepare or PrepareSpec()


def inspect_prepare_decision(
    workspace: str | Path,
    prepare: PrepareSpec | None = None,
    *,
    allow_normalize: bool = True,
) -> PrepareDecision:
    workspace_path = Path(workspace).resolve()
    spec = resolve_prepare_spec(prepare)
    has_data = workspace_has_runnable_data(workspace_path, allow_normalize=allow_normalize)

    if isinstance(spec.source, PrepareSourceExisting):
        if has_data:
            return PrepareDecision(action="reuse", reason="workspace 已存在可运行数据")
        return PrepareDecision(action="error", reason="workspace 缺少可运行数据，且未提供数据来源")

    if not has_data:
        return PrepareDecision(action="bootstrap", reason="workspace 缺少可运行数据，需要 bootstrap")

    if _prepare_source_matches_manifest(workspace_path, spec):
        return PrepareDecision(action="reuse", reason="传入数据来源与现有 manifest 同源，跳过 bootstrap")

    return PrepareDecision(action="error", reason="workspace 已存在数据，但传入数据来源不同或无法证明同源")


def prepare_workspace_data(workspace: str | Path, prepare: PrepareSpec | None = None) -> PrepareDecision:
    workspace_path = Path(workspace).resolve()
    spec = resolve_prepare_spec(prepare)
    decision = inspect_prepare_decision(workspace_path, spec, allow_normalize=True)
    if decision.action == "error":
        raise ValueError(decision.reason)
    if decision.action == "reuse":
        ensure_workspace_ready(workspace_path, allow_normalize=True)
        return decision

    xdev_dir = workspace_path / ".xdev"
    source = spec.source
    if isinstance(source, PrepareSourceSetId):
        import_from_set_id(
            source.set_id,
            source.base_url,
            xdev_dir,
            std_ids=source.std_ids,
            limit=source.limit,
        )
    elif isinstance(source, PrepareSourcePdfDir):
        import_from_pdfs(source.pdfs_dir, xdev_dir)
    elif isinstance(source, PrepareSourceDataDir):
        import_from_data_dir(source.data_dir, xdev_dir)
    elif isinstance(source, PrepareSourceConfigFile):
        import_from_source(source.source_file, xdev_dir)
    else:  # pragma: no cover - defensive
        raise ValueError(f"未知 prepare source: {source}")

    ensure_workspace_ready(workspace_path, allow_normalize=True)
    return decision


def _prepare_source_matches_manifest(workspace_path: Path, prepare: PrepareSpec) -> bool:
    manifest = get_manifest(workspace_path / ".xdev")
    if manifest is None:
        return False

    source = prepare.source
    manifest_source = manifest.source

    if isinstance(source, PrepareSourceSetId) and isinstance(manifest_source, DataSourceSetId):
        return (
            manifest_source.set_id == source.set_id
            and manifest_source.base_url == source.base_url
            and (manifest_source.std_ids or None) == (source.std_ids or None)
        )

    if isinstance(source, PrepareSourcePdfDir) and isinstance(manifest_source, DataSourcePdfs):
        return Path(manifest_source.pdf_dir).resolve() == Path(source.pdfs_dir).resolve()

    if isinstance(source, PrepareSourceDataDir) and isinstance(manifest_source, DataSourceDataDir):
        return Path(manifest_source.path).resolve() == Path(source.data_dir).resolve()

    if isinstance(source, PrepareSourceConfigFile):
        return False

    return isinstance(source, PrepareSourceExisting)
