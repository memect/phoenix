import asyncio
import json
import pytest

from agentscope.message import Msg
from fact_extract.agents import _create_toolkit
from fact_extract.agent_tools import tool_plan_task_add_batch
from fact_extract.records import (
    part_fact_add,
    part_fact_delete,
    part_fact_list,
    part_fact_update,
    part_get,
    plan_create,
    plan_get,
    plan_task_add,
    plan_task_delete,
    plan_task_list,
    plan_task_update,
)
from fact_extract.models import EvidenceItem, LLMSettings
from fact_extract._text import extract_json_object
import fact_extract.extractor as extractor_mod
import fact_extract.pipeline as pipeline_mod
from fact_extract.tracing import attach_agent_trace_hook
from fact_extract.evidence import normalize_extracted_facts


def test_plan_crud_flow(tmp_path):
    facts_dir = tmp_path / "facts"
    book_id = "book-demo"

    created = plan_create(
        facts_dir=facts_dir,
        book_id=book_id,
        doc="Demo Book",
        total_groups=20,
        profile={"domain": "mixed"},
        tasks=[
            {
                "task_id": "ch01",
                "chapter": "第一章",
                "groups": "1-8",
                "focus": "P0",
            }
        ],
    )
    assert created["book_id"] == book_id
    assert len(created["tasks"]) == 1

    loaded = plan_get(facts_dir=facts_dir, book_id=book_id)
    assert loaded["doc"] == "Demo Book"
    assert loaded["tasks"][0]["task_id"] == "ch01"

    task2 = plan_task_add(
        facts_dir=facts_dir,
        book_id=book_id,
        chapter="第二章",
        groups="9-15",
        focus="P1",
        task_id="ch02",
    )
    assert task2["task_id"] == "ch02"
    tasks = plan_task_list(facts_dir=facts_dir, book_id=book_id)
    assert len(tasks) == 2

    updated = plan_task_update(
        facts_dir=facts_dir,
        book_id=book_id,
        task_id="ch02",
        patch={"status": "done", "fact_count": 12},
    )
    assert updated["status"] == "done"
    assert updated["fact_count"] == 12

    deleted = plan_task_delete(
        facts_dir=facts_dir,
        book_id=book_id,
        task_id="ch01",
    )
    assert deleted is True
    tasks_after = plan_task_list(facts_dir=facts_dir, book_id=book_id)
    assert len(tasks_after) == 1
    assert tasks_after[0]["task_id"] == "ch02"


def test_part_fact_crud_flow(tmp_path):
    facts_dir = tmp_path / "facts"
    book_id = "book-demo"
    plan_create(
        facts_dir=facts_dir,
        book_id=book_id,
        doc="Demo Book",
        total_groups=20,
        profile={},
        tasks=[{"task_id": "ch01", "chapter": "第一章", "groups": "1-8", "focus": "P0"}],
    )

    added = part_fact_add(
        facts_dir=facts_dir,
        book_id=book_id,
        task_id="ch01",
        summary="约7万年前智人发生认知革命。",
        evidences=[
            {"text": "约7万年前，智人发生认知革命。", "group": 2},
            {"text": "认知革命使协作成为可能。", "group": 2},
        ],
        meta={"level": "L1", "priority": "P0", "type": "event"},
    )
    assert added["id"].startswith("fact_ch01_")
    assert len(added["source_ids"]) == 2

    part_payload = part_get(facts_dir=facts_dir, book_id=book_id, task_id="ch01")
    assert len(part_payload["facts"]) == 1
    assert part_payload["source_count"] == 2

    listed = part_fact_list(facts_dir=facts_dir, book_id=book_id, task_id="ch01")
    assert len(listed) == 1
    fact_id = listed[0]["id"]

    updated = part_fact_update(
        facts_dir=facts_dir,
        book_id=book_id,
        task_id="ch01",
        fact_id=fact_id,
        patch={"summary": "认知革命发生于约7万年前。"},
    )
    assert updated["summary"] == "认知革命发生于约7万年前。"

    deleted = part_fact_delete(
        facts_dir=facts_dir,
        book_id=book_id,
        task_id="ch01",
        fact_id=fact_id,
    )
    assert deleted is True
    listed_after = part_fact_list(facts_dir=facts_dir, book_id=book_id, task_id="ch01")
    assert listed_after == []

    manifest_path = facts_dir / "parts" / book_id / "ch01" / "manifest.part.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload == []


def test_plan_task_add_batch_tool_limit_and_write(tmp_path):
    facts_dir = tmp_path / "facts"
    book_id = "book-batch"
    plan_create(
        facts_dir=facts_dir,
        book_id=book_id,
        doc="Demo",
        total_groups=100,
        profile={},
        tasks=[],
    )

    tasks = [
        {"task_id": "ch01", "chapter": "第一章", "groups": "1-5", "focus": "P0"},
        {"task_id": "ch02", "chapter": "第二章", "groups": "6-10", "focus": "P1"},
    ]
    response = asyncio.run(
        tool_plan_task_add_batch(
            book_id=book_id,
            tasks=tasks,
            facts_dir=str(facts_dir),
        )
    )
    first_block = response.content[0]
    text = first_block["text"] if isinstance(first_block, dict) else first_block.text
    payload = json.loads(text)
    assert payload["count"] == 2

    plan = plan_get(facts_dir=facts_dir, book_id=book_id)
    assert len(plan["tasks"]) == 2
    assert plan["tasks"][0]["task_id"] == "ch01"
    assert plan["tasks"][1]["task_id"] == "ch02"

    too_many = [
        {"task_id": f"ch{index:02d}", "chapter": "章", "groups": "1-1", "focus": "P0"}
        for index in range(1, 33)
    ]
    with pytest.raises(ValueError):
        asyncio.run(
            tool_plan_task_add_batch(
                book_id=book_id,
                tasks=too_many,
                facts_dir=str(facts_dir),
            )
        )


def test_extract_json_object_prefers_last_balanced_json():
    text = """
FactPlannerAgent: tool call...
{"debug": true}
assistant final:
{"profile":{"domain":"fiction","focus_axes":["x"],"classification_notes":"ok"},"task_count":60,"persisted":true}
"""
    payload = extract_json_object(text)
    assert payload.get("task_count") == 60
    assert payload.get("persisted") is True


def test_extract_task_facts_llm_once_uses_single_call(monkeypatch):
    calls: list[str] = []

    def fake_chat_json(*, system_prompt, user_prompt):
        calls.append(user_prompt)
        return {
            "facts": [
                {
                    "summary": "测试事实",
                    "evidence_refs": ["ev_0001"],
                    "meta": {"level": "L1", "priority": "P0", "type": "event"},
                }
            ]
        }

    monkeypatch.setattr(LLMSettings, "chat_json", lambda self, **kw: fake_chat_json(**kw))
    llm = LLMSettings(model="demo", api_base="https://example.com", api_key="k", timeout=10.0)
    evidence_items = [
        EvidenceItem(evidence_id="ev_0001", group=1, text="证据一", kind="sentence", paragraph_index=0),
        EvidenceItem(evidence_id="ev_0002", group=2, text="证据二", kind="sentence", paragraph_index=0),
    ]
    facts, trace = extractor_mod._extract_task_facts_with_llm(
        evidence_items=evidence_items,
        task={"task_id": "ch01", "chapter": "第一章", "groups": "1-2", "focus": "P0"},
        llm=llm,
        max_chunk_chars=0,
        reflect=False,
    )
    assert len(calls) == 1
    assert "[ev_0001]" in calls[0]
    assert "[ev_0002]" in calls[0]
    assert trace["bundle_count"] == 1
    assert len(facts) >= 1


def test_materialize_part_outputs_groups_sources_by_group(tmp_path):
    part_dir = tmp_path / "part"
    (part_dir / "sources").mkdir(parents=True, exist_ok=True)
    evidence_map = {
        "ev_0001": EvidenceItem(evidence_id="ev_0001", group=1, text="第一句证据", kind="sentence", paragraph_index=0),
        "ev_0002": EvidenceItem(evidence_id="ev_0002", group=1, text="第二句证据", kind="sentence", paragraph_index=0),
        "ev_0003": EvidenceItem(evidence_id="ev_0003", group=2, text="第三句证据", kind="sentence", paragraph_index=0),
    }
    extracted_facts = [
        {
            "summary": "测试事实",
            "evidence_refs": ["ev_0001", "ev_0003"],
            "meta": {"level": "L1"},
        }
    ]
    group_body_map = {
        1: "第1页整页正文A\n第1页整页正文B",
        2: "第2页整页正文",
    }

    manifest_part, source_count = extractor_mod._materialize_part_outputs(
        part_dir=part_dir,
        doc="Demo Book",
        task_id="ch01",
        extracted_facts=extracted_facts,
        evidence_registry=evidence_map,
    )

    assert len(manifest_part) == 1
    assert source_count == 3
    source_ids = manifest_part[0]["source_ids"]
    assert source_ids == ["ev_0001", "ev_0003"]

    source1_text = (part_dir / "sources" / "ev_0001.txt").read_text(encoding="utf-8")
    source1_meta = json.loads((part_dir / "sources" / "ev_0001.json").read_text(encoding="utf-8"))
    source2_text = (part_dir / "sources" / "ev_0003.txt").read_text(encoding="utf-8")
    source2_meta = json.loads((part_dir / "sources" / "ev_0003.json").read_text(encoding="utf-8"))

    assert source1_meta["group"] == 1
    assert source2_meta["group"] == 2
    assert source1_text == "第一句证据"
    assert source2_text == "第三句证据"


def test_normalize_extracted_facts_keeps_summary_and_all_group_refs():
    long_summary = "这是一条很长的事实摘要。" * 40
    evidence_refs = [f"e{i}" for i in range(1, 81)]
    registry = {f"e{i}": EvidenceItem(evidence_id=f"e{i}", group=i, text=f"证据{i}", kind="sentence", paragraph_index=0) for i in range(1, 81)}
    facts = normalize_extracted_facts(
        [{"summary": long_summary, "evidence_refs": evidence_refs}],
        evidence_registry=registry,
    )
    assert len(facts) == 1
    assert facts[0]["summary"] == long_summary
    assert facts[0]["evidence_refs"] == evidence_refs


def test_worker_fact_add_batch_allows_evidence_refs_outside_task_range(tmp_path):
    worker_toolkit = _create_toolkit(
        enable_tools=True,
        role="worker",
        pdf_path="/tmp/demo.pdf",
        docjson_path="/tmp/demo.json",
        facts_dir=str(tmp_path / "facts"),
        worker_context={
            "book_id": "book-demo",
            "task_id": "ch01",
            "doc": "Demo",
            "group_start": 1,
            "group_end": 10,
            "group_text_by_group": {
                99: "第99页整页正文",
            },
            "evidence_registry": {
                "e99": EvidenceItem(evidence_id="e99", group=99, text="第99页整页正文", kind="sentence", paragraph_index=0),
            },
        },
    )
    add_fn = worker_toolkit.tools["tool_worker_fact_add_batch"].original_func
    response = asyncio.run(
        add_fn(
            facts=[{"summary": "跨范围证据事实", "evidence_refs": ["e99"]}],
        )
    )
    first_block = response.content[0]
    text = first_block["text"] if isinstance(first_block, dict) else first_block.text
    payload = json.loads(text)
    assert payload["ok"] is True
    assert payload["data"]["saved"] == 1


def test_part_get_is_read_only_for_missing_part(tmp_path):
    facts_dir = tmp_path / "facts"
    payload = part_get(facts_dir=facts_dir, book_id="unknown", task_id="ch01")
    assert payload == {
        "book_id": "unknown",
        "task_id": "ch01",
        "facts": [],
        "source_count": 0,
    }
    assert not (facts_dir / "parts" / "unknown" / "ch01").exists()


def test_toolkit_role_isolation_for_planner_and_worker():
    planner_toolkit = _create_toolkit(
        enable_tools=True,
        role="planner",
        pdf_path="/tmp/demo.pdf",
        docjson_path="/tmp/demo.json",
        facts_dir="/tmp/facts",
    )
    planner_tools = set(planner_toolkit.tools.keys())
    assert "tool_plan_get" in planner_tools
    assert "tool_plan_task_add_batch" in planner_tools
    assert "tool_part_fact_add" not in planner_tools

    worker_toolkit = _create_toolkit(
        enable_tools=True,
        role="worker",
        pdf_path="/tmp/demo.pdf",
        docjson_path="/tmp/demo.json",
        facts_dir="/tmp/facts",
        worker_context={
            "book_id": "book-demo",
            "task_id": "ch01",
            "doc": "Demo",
            "group_start": 1,
            "group_end": 10,
            "group_text_by_group": {1: "第1页正文"},
        },
    )
    worker_tools = set(worker_toolkit.tools.keys())
    assert "tool_pdf_explorer" in worker_tools
    assert "tool_plan_get" not in worker_tools
    assert "tool_part_fact_add" not in worker_tools
    assert "tool_worker_context_get" in worker_tools
    assert "tool_worker_fact_add_batch" in worker_tools
    assert "tool_worker_part_stats" in worker_tools


def test_agentic_worker_text_reply_without_json_is_allowed(tmp_path, monkeypatch):
    facts_dir = tmp_path / "facts"
    part_dir = facts_dir / "parts" / "book-demo" / "ch01"
    (part_dir / "sources").mkdir(parents=True, exist_ok=True)
    captured_kwargs: dict[str, object] = {}

    def fake_create_worker_agent(**kwargs):
        captured_kwargs.update(kwargs)
        return object()

    async def fake_call_agent_silently(agent, message, *, timeout_sec=None, stream_log_path=None):
        _ = (agent, message, timeout_sec, stream_log_path)
        return "done saved=0 failed=0", "tool trace"

    monkeypatch.setattr("fact_extract.agents.create_worker_agent", fake_create_worker_agent)
    monkeypatch.setattr(extractor_mod, "call_agent_silently", fake_call_agent_silently)

    llm = LLMSettings(model="demo", api_base="https://example.com", api_key="k", timeout=10.0)
    evidence_items = [
        EvidenceItem(evidence_id="ev_0001", group=1, text="证据一", kind="sentence", paragraph_index=0),
    ]
    stats, trace = extractor_mod._extract_task_facts_with_agentic(
        facts_dir=facts_dir,
        book_id="book-demo",
        doc="Demo",
        pdf_path=None,
        docjson_path=None,
        evidence_items=evidence_items,
        task={"task_id": "ch01", "chapter": "第一章", "groups": "1-2", "focus": "P0"},
        group_start=1,
        group_end=2,
        group_body_map={1: "第1页正文"},
        llm=llm,
        max_chunk_chars=2000,
    )

    assert stats["fact_count"] == 0
    assert stats["source_count"] == 0
    assert trace["backend"] == "agentic"
    assert (part_dir / "manifest.part.json").exists()
    assert captured_kwargs["worker_book_id"] == "book-demo"
    assert captured_kwargs["worker_task_id"] == "ch01"
    assert captured_kwargs["worker_group_start"] == 1
    assert captured_kwargs["worker_group_end"] == 2


def test_call_agent_silently_writes_per_agent_conversation_stream(tmp_path):
    class FakeResponse:
        def get_text_content(self):
            return "done saved=1 failed=0"

    async def fake_agent(message):
        _ = message
        return FakeResponse()

    class FakeMessage:
        def __init__(self, content: str):
            self.content = content

    stream_path = tmp_path / "worker.stream.log"
    text, tool_log = asyncio.run(
        extractor_mod.call_agent_silently(
            fake_agent,
            FakeMessage("payload-user"),
            timeout_sec=None,
            stream_log_path=stream_path,
        )
    )

    assert text == "done saved=1 failed=0"
    assert tool_log == ""
    stream_text = stream_path.read_text(encoding="utf-8")
    assert "payload-user" in stream_text
    assert "done saved=1 failed=0" in stream_text


def test_attach_agent_trace_hook_writes_tool_use_blocks(tmp_path):
    class FakeAgent:
        def __init__(self):
            self._disable_console_output = False
            self.hooks: dict[str, object] = {}

        def register_instance_hook(self, hook_type: str, hook_name: str, hook):
            self.hooks[f"{hook_type}:{hook_name}"] = hook

    stream_path = tmp_path / "trace.stream.log"
    agent = FakeAgent()
    attach_agent_trace_hook(agent, stream_log_path=stream_path)

    hook = agent.hooks["pre_print:fact_extract_stream_trace"]
    msg = Msg(
        name="FactWorkerAgent",
        role="assistant",
        content=[
            {"type": "text", "text": "先调用工具"},
            {"type": "tool_use", "id": "call_1", "name": "tool_worker_context_get", "input": {}},
        ],
    )
    hook(agent, {"msg": msg, "last": True, "speech": None})

    assert agent._disable_console_output is True
    content = stream_path.read_text(encoding="utf-8")
    assert "FactWorkerAgent: 先调用工具" in content
    assert "\"type\": \"tool_use\"" in content


def test_run_plan_workers_marks_rerun_tasks_pending_first(tmp_path, monkeypatch):
    facts_dir = tmp_path / "facts"
    book_id = "book-workers"
    plan = plan_create(
        facts_dir=facts_dir,
        book_id=book_id,
        doc="Demo",
        total_groups=20,
        profile={},
        tasks=[
            {"task_id": "ch01", "chapter": "第一章", "groups": "1-10", "focus": "P0"},
            {"task_id": "ch02", "chapter": "第二章", "groups": "11-20", "focus": "P1"},
        ],
    )
    for task in plan["tasks"]:
        task["status"] = "done"
        task["fact_count"] = 9
        task["source_count"] = 9
        task["error"] = "old"
    plan_path = facts_dir / "plans" / f"{book_id}.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

    seen_status: list[str] = []
    seen_fact_count: list[int] = []

    def fake_execute_task(*, task, **kwargs):
        _ = kwargs
        seen_status.append(str(task.get("status")))
        seen_fact_count.append(int(task.get("fact_count", -1)))
        return {
            "status": "done",
            "task_id": str(task.get("task_id")),
            "fact_count": 1,
            "source_count": 1,
            "error": "",
        }

    monkeypatch.setattr(pipeline_mod, "execute_task", fake_execute_task)
    result = pipeline_mod.run_plan_workers(
        facts_dir=facts_dir,
        plan_path=plan_path,
        max_workers=1,
        extractor_backend="mock",
        only_pending=False,
    )

    assert result.task_count == 2
    assert seen_status == ["pending", "pending"]
    assert seen_fact_count == [0, 0]


def test_run_single_task_marks_task_pending_first(tmp_path, monkeypatch):
    facts_dir = tmp_path / "facts"
    book_id = "book-single"
    plan = plan_create(
        facts_dir=facts_dir,
        book_id=book_id,
        doc="Demo",
        total_groups=10,
        profile={},
        tasks=[
            {"task_id": "ch01", "chapter": "第一章", "groups": "1-10", "focus": "P0"},
        ],
    )
    plan["tasks"][0]["status"] = "done"
    plan["tasks"][0]["fact_count"] = 5
    plan["tasks"][0]["source_count"] = 7
    plan["tasks"][0]["error"] = "old"
    plan_path = facts_dir / "plans" / f"{book_id}.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

    observed: dict[str, object] = {}

    def fake_execute_task(*, task, **kwargs):
        _ = kwargs
        observed["status"] = task.get("status")
        observed["fact_count"] = task.get("fact_count")
        observed["source_count"] = task.get("source_count")
        observed["error"] = task.get("error")
        return {
            "status": "done",
            "task_id": str(task.get("task_id")),
            "fact_count": 2,
            "source_count": 3,
            "error": "",
        }

    monkeypatch.setattr(pipeline_mod, "execute_task", fake_execute_task)
    pipeline_mod.run_single_task(
        facts_dir=facts_dir,
        plan_path=plan_path,
        task_id="ch01",
        extractor_backend="mock",
    )

    assert observed == {
        "status": "pending",
        "fact_count": 0,
        "source_count": 0,
        "error": "",
    }
