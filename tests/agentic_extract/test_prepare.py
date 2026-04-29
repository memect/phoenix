import json

import pytest

from agentic_extract.prepare import inspect_prepare_decision, prepare_workspace_data
from agentic_extract.types import (
    PrepareSourceDataDir,
    PrepareSourceExisting,
    PrepareSourcePdfDir,
    PrepareSourceSetId,
    PrepareSpec,
)


def _write_manifest(workspace, payload):
    xdev_dir = workspace / ".xdev"
    (xdev_dir / "data" / "docjson").mkdir(parents=True, exist_ok=True)
    (xdev_dir / "data" / "docjson" / "doc1.json").write_text("{}", encoding="utf-8")
    (xdev_dir / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_inspect_prepare_decision_errors_when_existing_data_required_but_missing(tmp_path):
    decision = inspect_prepare_decision(tmp_path, PrepareSpec(source=PrepareSourceExisting()))

    assert decision.action == "error"


def test_inspect_prepare_decision_bootstraps_when_source_given_and_data_missing(tmp_path):
    decision = inspect_prepare_decision(
        tmp_path,
        PrepareSpec(source=PrepareSourcePdfDir(pdfs_dir=str(tmp_path / "pdfs"))),
    )

    assert decision.action == "bootstrap"


def test_inspect_prepare_decision_reuses_when_pdf_source_matches_manifest(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    _write_manifest(
        tmp_path,
        {
            "source": {"type": "pdfs", "pdf_dir": str(pdf_dir.resolve())},
            "imported_at": "2026-01-01T00:00:00",
            "doc_count": 1,
        },
    )

    decision = inspect_prepare_decision(
        tmp_path,
        PrepareSpec(source=PrepareSourcePdfDir(pdfs_dir=str(pdf_dir))),
    )

    assert decision.action == "reuse"


def test_inspect_prepare_decision_errors_when_source_differs(tmp_path):
    data_dir = tmp_path / "data-source"
    data_dir.mkdir()
    _write_manifest(
        tmp_path,
        {
            "source": {"type": "data-dir", "path": str(data_dir.resolve())},
            "imported_at": "2026-01-01T00:00:00",
            "doc_count": 1,
        },
    )

    decision = inspect_prepare_decision(
        tmp_path,
        PrepareSpec(source=PrepareSourceSetId(set_id="set-1", base_url="http://example.com")),
    )

    assert decision.action == "error"


def test_prepare_workspace_data_reuses_existing_data(tmp_path):
    data_dir = tmp_path / "data-source"
    data_dir.mkdir()
    _write_manifest(
        tmp_path,
        {
            "source": {"type": "data-dir", "path": str(data_dir.resolve())},
            "imported_at": "2026-01-01T00:00:00",
            "doc_count": 1,
        },
    )

    decision = prepare_workspace_data(
        tmp_path,
        PrepareSpec(source=PrepareSourceDataDir(data_dir=str(data_dir))),
    )

    assert decision.action == "reuse"


def test_inspect_prepare_decision_can_skip_normalize_for_dry_run(tmp_path):
    docjson_dir = tmp_path / ".xdev" / "data" / "docjson"
    docjson_dir.mkdir(parents=True)
    (docjson_dir / "doc1.json").write_text("{}", encoding="utf-8")

    decision = inspect_prepare_decision(
        tmp_path,
        PrepareSpec(source=PrepareSourceExisting()),
        allow_normalize=False,
    )

    assert decision.action == "error"
    assert not (tmp_path / ".xdev" / "manifest.json").exists()


def test_prepare_workspace_data_raises_on_conflicting_source(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    other_pdf_dir = tmp_path / "other-pdfs"
    pdf_dir.mkdir()
    other_pdf_dir.mkdir()
    _write_manifest(
        tmp_path,
        {
            "source": {"type": "pdfs", "pdf_dir": str(pdf_dir.resolve())},
            "imported_at": "2026-01-01T00:00:00",
            "doc_count": 1,
        },
    )

    with pytest.raises(ValueError, match="不同或无法证明同源"):
        prepare_workspace_data(
            tmp_path,
            PrepareSpec(source=PrepareSourcePdfDir(pdfs_dir=str(other_pdf_dir))),
        )
