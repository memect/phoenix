import json
from pathlib import Path

import pytest

from xdev.config import XdevConfig
from xdev.setup import XdevExtractionRuntime


SIMPLE_DOCJSON = {
    "tree": {
        "root": {
            "id": 0,
            "type": "title",
            "parent_path": [],
            "page_number": 0,
            "data": {"text": "", "textlines": []},
            "children": [
                {
                    "id": 1,
                    "type": "title",
                    "parent_path": [],
                    "page_number": 1,
                    "data": {"text": "测试标题"},
                    "children": [],
                }
            ],
        }
    },
    "pages": [{"number": 1, "bbox": [0, 0, 100, 100]}],
}


TOOL_HUB_PROGRAM = """
from code_executor.document.models.document import Document


def extract(document: Document, tool_hub):
    return {
        "tool": tool_hub["name"],
        "texts": document.get_all_texts(),
    }
"""


def _runtime(name: str = "runtime-hub") -> XdevExtractionRuntime:
    return XdevExtractionRuntime(
        concurrent=3,
        memect_api_base="http://pdf-parser.example/api",
        tool_hub={"name": name},
        config=XdevConfig(),
    )


def _write_workspace(tmp_path: Path, program: str = TOOL_HUB_PROGRAM) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "program.py").write_text(program, encoding="utf-8")
    return workspace


def _write_data_dir(tmp_path: Path, doc_id: str = "doc1") -> Path:
    data_dir = tmp_path / ".xdev"
    docjson_dir = data_dir / "data" / "docjson"
    labels_dir = data_dir / "labels"
    docjson_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)
    (docjson_dir / f"{doc_id}.json").write_text(
        json.dumps(SIMPLE_DOCJSON, ensure_ascii=False),
        encoding="utf-8",
    )
    (labels_dir / f"{doc_id}.json").write_text(
        json.dumps({"field": "value"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (data_dir / "schema.json").write_text(
        json.dumps({"type": "object", "data": {"field": "str"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    return data_dir


@pytest.mark.asyncio
async def test_extract_from_docjson_injects_runtime_tool_hub(monkeypatch):
    from xdev.extract import extract_from_docjson

    monkeypatch.setattr("xdev.setup.prepare_extraction_runtime", lambda: _runtime())

    result = await extract_from_docjson(SIMPLE_DOCJSON, program=TOOL_HUB_PROGRAM)

    assert result["tool"] == "runtime-hub"
    assert "测试标题" in result["texts"]


@pytest.mark.asyncio
async def test_extract_from_docjson_config_mode_raises(monkeypatch):
    from xdev.extract import extract_from_docjson

    monkeypatch.setattr("xdev.setup.prepare_extraction_runtime", lambda: _runtime())

    with pytest.raises(ValueError, match="config/flat 旧格式已不再支持"):
        await extract_from_docjson(
            SIMPLE_DOCJSON,
            config={"field": "def extract(article): return {'field': ''}"},
        )


def test_run_single_extraction_injects_runtime_tool_hub(tmp_path, monkeypatch):
    from xdev.evaluation import run_single_extraction

    data_dir = _write_data_dir(tmp_path)
    workspace = _write_workspace(tmp_path)
    monkeypatch.setattr("xdev.evaluation.prepare_extraction_runtime", lambda: _runtime())

    result = run_single_extraction("doc1", data_dir=str(data_dir), workspace=str(workspace))

    assert result["tool"] == "runtime-hub"
    assert "测试标题" in result["texts"]


def test_run_single_extraction_from_file_injects_runtime_tool_hub(tmp_path, monkeypatch):
    from xdev.evaluation import run_single_extraction_from_file

    data_dir = _write_data_dir(tmp_path)
    workspace = _write_workspace(tmp_path)
    monkeypatch.setattr("xdev.evaluation.prepare_extraction_runtime", lambda: _runtime())

    result = run_single_extraction_from_file(
        workspace=str(workspace),
        docjson_path=str(data_dir / "data" / "docjson" / "doc1.json"),
    )

    assert result["tool"] == "runtime-hub"
    assert "测试标题" in result["texts"]


def test_run_evaluation_passes_runtime_tool_hub_to_batch(tmp_path, monkeypatch):
    from evaluator.evaluators.object.models import ObjectEvaluationResult
    from xdev.evaluation import run_evaluation

    captured: dict = {}
    data_dir = _write_data_dir(tmp_path)
    workspace = _write_workspace(
        tmp_path,
        """
from code_executor.document.models.document import Document


def extract(document: Document, tool_hub):
    return {"field": tool_hub["name"]}
""",
    )
    monkeypatch.setattr("xdev.evaluation.prepare_extraction_runtime", lambda: _runtime("eval-hub"))

    async def fake_batch_execute_on_docjsons(**kwargs):
        captured.update(kwargs)
        return [{"index": 0, "success": True, "data": {"field": "value"}, "error": None}]

    monkeypatch.setattr(
        "code_executor.api.batch_execute_on_docjsons",
        fake_batch_execute_on_docjsons,
    )

    result = run_evaluation(doc_ids=["doc1"], data_dir=str(data_dir), workspace=str(workspace))

    assert captured["tool_hub"] == {"name": "eval-hub"}
    assert captured["concurrent"] == 3
    assert isinstance(result.result, ObjectEvaluationResult)
