import json

import pytest
from agentscope.message import Msg

from agentic_extract.events import EventWriter, event_writer_scope
from agentic_extract.hooks import register_agent_logging
from agentic_extract.runtime import runtime_scope


class FakeMemory:
    def __init__(self):
        self.items = []

    async def add(self, msg):
        self.items.append(msg)


class FakeHookAgent:
    def __init__(self, name="DevAgent"):
        self.name = name
        self.memory = FakeMemory()
        self.registered = {}

    def register_instance_hook(self, hook_type, hook_name, hook):
        self.registered[(hook_type, hook_name)] = hook


@pytest.mark.asyncio
async def test_agent_hooks_write_structured_messages_to_events_jsonl(tmp_path):
    agent = FakeHookAgent()
    register_agent_logging(agent)

    writer = EventWriter.for_workspace(tmp_path, entrypoint="run")
    input_msg = Msg(name="Supervisor", content="implement field", role="user")
    reply_msg = Msg(name="DevAgent", content="done", role="assistant")
    observed_msg = Msg(name="Evaluator", content="accuracy=90%", role="user")

    with event_writer_scope(writer):
        with runtime_scope(iteration=2, step="dev_agent"):
            await agent.registered[("pre_reply", "agent_event_call_start")](
                agent,
                {"msg": input_msg, "structured_model": None},
            )
            await agent.registered[("post_print", "agent_logging")](
                agent,
                {"msg": reply_msg, "last": True},
                None,
            )
            await agent.registered[("post_observe", "agent_event_observe")](
                agent,
                {"msg": observed_msg},
                None,
            )
            await agent.registered[("post_reply", "agent_event_call_end")](
                agent,
                {"msg": input_msg, "structured_model": None},
                reply_msg,
            )

    lines = [
        json.loads(line)
        for line in (tmp_path / ".agent_state" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert [line["type"] for line in lines] == [
        "agent_call_started",
        "agent_message",
        "agent_message",
        "agent_call_completed",
    ]
    assert lines[0]["input_messages"][0]["content"] == "implement field"
    assert lines[1]["source"] == "print"
    assert lines[1]["message"]["content"] == "done"
    assert lines[1]["call_id"] == lines[0]["call_id"]
    assert lines[1]["iteration"] == 2
    assert lines[2]["source"] == "observe"
    assert lines[2]["message"]["content"] == "accuracy=90%"
    assert lines[3]["reply_message_id"] == reply_msg.id
