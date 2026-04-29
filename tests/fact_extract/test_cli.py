import json
from pathlib import Path

from click.testing import CliRunner

from fact_extract.cli import cli
from fact_extract import pipeline as pipeline_mod


def _write_fixture_docjson(path: Path) -> None:
    docjson = {
        "pages": [{}, {}, {}, {}, {}],
        "tree": {
            "root": {
                "type": "title",
                "page_number": 1,
                "data": {"text": "测试书"},
                "children": [
                    {
                        "type": "title",
                        "page_number": 1,
                        "data": {"text": "目录"},
                        "children": [],
                    },
                    {
                        "type": "section",
                        "page_number": 1,
                        "data": {
                            "textlines": [
                                {"text": "目录", "page_number": 1},
                                {"text": "第一章..........2", "page_number": 1},
                                {"text": "第二章..........4", "page_number": 1},
                            ]
                        },
                        "children": [],
                    },
                    {
                        "type": "title",
                        "page_number": 2,
                        "data": {"text": "第一章 起源"},
                        "children": [],
                    },
                    {
                        "type": "section",
                        "page_number": 2,
                        "data": {
                            "textlines": [
                                {"text": "约7万年前，智人发生认知革命。", "page_number": 2},
                                {"text": "认知革命使得大规模协作成为可能。", "page_number": 2},
                            ]
                        },
                        "children": [],
                    },
                    {
                        "type": "section",
                        "page_number": 3,
                        "data": {
                            "textlines": [
                                {"text": "农业革命发生于约1.2万年前。", "page_number": 3},
                                {"text": "农业革命导致人口增长。", "page_number": 3},
                            ]
                        },
                        "children": [],
                    },
                    {
                        "type": "title",
                        "page_number": 4,
                        "data": {"text": "第二章 扩散"},
                        "children": [],
                    },
                    {
                        "type": "section",
                        "page_number": 4,
                        "data": {
                            "textlines": [
                                {"text": "智人扩散到欧亚大陆。", "page_number": 4},
                                {"text": "尼安德特人与智人存在竞争。", "page_number": 4},
                            ]
                        },
                        "children": [],
                    },
                    {
                        "type": "section",
                        "page_number": 5,
                        "data": {
                            "textlines": [
                                {"text": "作者认为虚构秩序塑造了现代社会。", "page_number": 5},
                                {"text": "未来可能出现新的技术革命。", "page_number": 5},
                            ]
                        },
                        "children": [],
                    },
                ],
            }
        },
    }
    path.write_text(json.dumps(docjson, ensure_ascii=False), encoding="utf-8")


def test_plan_workers_merge_flow(tmp_path):
    runner = CliRunner()
    facts_dir = tmp_path / "facts"
    pdf_path = tmp_path / "book.pdf"
    docjson_path = tmp_path / "book.json"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    _write_fixture_docjson(docjson_path)

    result_init = runner.invoke(cli, ["init", "--facts-dir", str(facts_dir)])
    assert result_init.exit_code == 0, result_init.output

    result_plan = runner.invoke(
        cli,
        [
            "plan",
            "--pdf",
            str(pdf_path),
            "--docjson",
            str(docjson_path),
            "--planner-backend",
            "mock",
            "--no-explorer",
            "--facts-dir",
            str(facts_dir),
        ],
    )
    assert result_plan.exit_code == 0, result_plan.output
    plan_payload = json.loads(result_plan.output)
    plan_path = Path(plan_payload["plan_path"])
    assert plan_path.exists()
    assert plan_payload["task_count"] >= 1

    plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
    assert {"book_id", "doc", "total_groups", "profile", "tasks"} <= set(plan_data.keys())
    first_task = plan_data["tasks"][0]
    assert {"task_id", "chapter", "groups", "group_count", "focus"} <= set(first_task.keys())

    result_workers = runner.invoke(
        cli,
        [
            "run-workers",
            "--plan",
            str(plan_path),
            "--extractor-backend",
            "mock",
            "--facts-dir",
            str(facts_dir),
        ],
    )
    assert result_workers.exit_code == 0, result_workers.output
    worker_payload = json.loads(result_workers.output)
    assert worker_payload["success_count"] >= 1

    result_merge = runner.invoke(
        cli,
        [
            "merge",
            "--plan",
            str(plan_path),
            "--facts-dir",
            str(facts_dir),
        ],
    )
    assert result_merge.exit_code == 0, result_merge.output
    merge_payload = json.loads(result_merge.output)
    assert merge_payload["merged_facts"] >= 1

    manifest = json.loads((facts_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest
    first_fact = manifest[0]
    assert {"id", "summary", "source_ids"} <= set(first_fact.keys())
    assert first_fact["id"].startswith("fact_")
    assert first_fact["source_ids"]

    source_id = first_fact["source_ids"][0]
    source_text = (facts_dir / "sources" / f"{source_id}.txt").read_text(encoding="utf-8")
    source_meta = json.loads((facts_dir / "sources" / f"{source_id}.json").read_text(encoding="utf-8"))
    assert source_text.strip()
    assert {"doc", "group"} <= set(source_meta.keys())


def test_run_command_handles_multiple_pdfs(tmp_path):
    runner = CliRunner()
    facts_dir = tmp_path / "facts"

    pdf_a = tmp_path / "a.pdf"
    pdf_b = tmp_path / "b.pdf"
    docjson_a = tmp_path / "a.json"
    docjson_b = tmp_path / "b.json"
    pdf_a.write_bytes(b"%PDF-1.4\n")
    pdf_b.write_bytes(b"%PDF-1.4\n")
    _write_fixture_docjson(docjson_a)
    _write_fixture_docjson(docjson_b)

    result = runner.invoke(
        cli,
        [
            "run",
            "--pdf",
            str(pdf_a),
            "--pdf",
            str(pdf_b),
            "--docjson",
            str(docjson_a),
            "--docjson",
            str(docjson_b),
            "--planner-backend",
            "mock",
            "--extractor-backend",
            "mock",
            "--no-explorer",
            "--facts-dir",
            str(facts_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload["documents"]) == 2

    manifest = json.loads((facts_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) >= 2
    assert manifest[0]["id"].startswith("fact_")

    current_state = json.loads((facts_dir / "logs" / "current.json").read_text(encoding="utf-8"))
    assert current_state["status"] in {"completed", "running"} or str(current_state["status"]).startswith("failed")
    assert (facts_dir / "logs" / "stages").exists()


def test_run_from_extract_skips_plan_and_records_failed_task(tmp_path, monkeypatch):
    runner = CliRunner()
    facts_dir = tmp_path / "facts"
    pdf_path = tmp_path / "book.pdf"
    docjson_path = tmp_path / "book.json"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    _write_fixture_docjson(docjson_path)

    result_plan = runner.invoke(
        cli,
        [
            "plan",
            "--pdf",
            str(pdf_path),
            "--docjson",
            str(docjson_path),
            "--planner-backend",
            "mock",
            "--no-explorer",
            "--facts-dir",
            str(facts_dir),
        ],
    )
    assert result_plan.exit_code == 0, result_plan.output
    plan_payload = json.loads(result_plan.output)
    plan_path = Path(plan_payload["plan_path"])
    plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
    if len(plan_data.get("tasks", [])) < 2:
        result_add = runner.invoke(
            cli,
            [
                "plan-task-add",
                "--book-id",
                plan_data["book_id"],
                "--chapter",
                "补充任务",
                "--groups",
                "4-5",
                "--focus",
                "P0",
                "--task-id",
                "ch_extra",
                "--facts-dir",
                str(facts_dir),
            ],
        )
        assert result_add.exit_code == 0, result_add.output
        plan_data = json.loads(plan_path.read_text(encoding="utf-8"))

    failed_task_id = plan_data["tasks"][0]["task_id"]
    original_execute = pipeline_mod.execute_task

    def _patched_execute_task(*args, **kwargs):
        task = kwargs.get("task")
        if isinstance(task, dict) and task.get("task_id") == failed_task_id:
            raise RuntimeError("forced worker failure")
        return original_execute(*args, **kwargs)

    monkeypatch.setattr(pipeline_mod, "execute_task", _patched_execute_task)

    result_run = runner.invoke(
        cli,
        [
            "run",
            "--from",
            "extract",
            "--plan",
            str(plan_path),
            "--extractor-backend",
            "mock",
            "--facts-dir",
            str(facts_dir),
        ],
    )
    assert result_run.exit_code == 0, result_run.output
    payload = json.loads(result_run.output)
    assert len(payload["documents"]) == 1
    assert payload["documents"][0]["failed_tasks"] >= 1

    plan_after = json.loads(plan_path.read_text(encoding="utf-8"))
    failed_tasks = [item for item in plan_after["tasks"] if item["status"] == "failed"]
    assert failed_tasks
    assert "forced worker failure" in failed_tasks[0]["error"]

    error_path = facts_dir / "parts" / plan_after["book_id"] / failed_task_id / "error.json"
    assert error_path.exists()
    error_payload = json.loads(error_path.read_text(encoding="utf-8"))
    assert "forced worker failure" in error_payload["error"]
    assert error_payload["agent_log_path"].endswith(f"/worker_{failed_task_id}.jsonl")
    assert error_payload["agent_stream_log_path"].endswith(f"/worker_{failed_task_id}.stream.log")

    manifest = json.loads((facts_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest
