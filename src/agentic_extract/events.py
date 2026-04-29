"""Structured event logging for agentic_extract runs."""

from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from agentscope.message import Msg

from .types import ProgressEvent, utc_now

_current_event_writer: ContextVar["EventWriter | None"] = ContextVar(
    "agentic_extract_current_event_writer",
    default=None,
)


def _to_utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return _to_utc_iso(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Msg):
        return value.to_dict()
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return str(value)


@dataclass
class EventWriter:
    workspace: Path
    entrypoint: str
    path: Path
    run_id: str
    seq: int = 0

    @classmethod
    def for_workspace(
        cls,
        workspace: str | Path,
        *,
        entrypoint: str,
    ) -> "EventWriter":
        workspace_path = Path(workspace).expanduser().resolve()
        agent_state_dir = workspace_path / ".agent_state"
        agent_state_dir.mkdir(parents=True, exist_ok=True)
        started_at = utc_now().strftime("%Y%m%dT%H%M%SZ")
        return cls(
            workspace=workspace_path,
            entrypoint=entrypoint,
            path=agent_state_dir / "events.jsonl",
            run_id=f"{started_at}-{uuid4().hex[:8]}",
        )

    def write(
        self,
        event_type: str,
        *,
        category: str,
        timestamp: datetime | None = None,
        **payload: Any,
    ) -> dict[str, Any]:
        self.seq += 1
        record = {
            "schema_version": 1,
            "run_id": self.run_id,
            "seq": self.seq,
            "timestamp": _to_utc_iso(timestamp or utc_now()),
            "workspace": str(self.workspace),
            "entrypoint": self.entrypoint,
            "category": category,
            "type": event_type,
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=_json_default))
            fh.write("\n")
        return record


def get_current_event_writer() -> EventWriter | None:
    return _current_event_writer.get()


@contextmanager
def event_writer_scope(writer: EventWriter) -> Iterator[None]:
    token: Token = _current_event_writer.set(writer)
    try:
        yield
    finally:
        _current_event_writer.reset(token)


def emit_event(
    event_type: str,
    *,
    category: str,
    timestamp: datetime | None = None,
    **payload: Any,
) -> dict[str, Any] | None:
    writer = get_current_event_writer()
    if writer is None:
        return None
    return writer.write(
        event_type,
        category=category,
        timestamp=timestamp,
        **payload,
    )


def emit_progress_event(event: ProgressEvent) -> dict[str, Any] | None:
    payload = event.model_dump(mode="json")
    event_type = payload.pop("type")
    timestamp = payload.pop("timestamp", None)
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return emit_event(
        event_type,
        category="progress",
        timestamp=timestamp,
        **payload,
    )


def _serialize_msg(value: Msg) -> dict[str, Any]:
    return value.to_dict()


def _serialize_messages(value: Msg | list[Msg] | None) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_serialize_msg(msg) for msg in value]
    return [_serialize_msg(value)]


def emit_agent_call_started(
    *,
    agent: str,
    call_id: str,
    input_messages: Msg | list[Msg] | None,
    structured_output_model: str | None = None,
) -> dict[str, Any] | None:
    from .runtime import get_current_scope

    scope = get_current_scope()
    return emit_event(
        "agent_call_started",
        category="agent",
        agent=agent,
        call_id=call_id,
        iteration=scope.iteration,
        step=scope.step,
        phase=scope.phase,
        input_messages=_serialize_messages(input_messages),
        structured_output_model=structured_output_model,
    )


def emit_agent_call_completed(
    *,
    agent: str,
    call_id: str | None,
    reply_message: Msg | None,
    max_iters_reached: bool = False,
) -> dict[str, Any] | None:
    from .runtime import get_current_scope

    scope = get_current_scope()
    return emit_event(
        "agent_call_completed",
        category="agent",
        agent=agent,
        call_id=call_id,
        iteration=scope.iteration,
        step=scope.step,
        phase=scope.phase,
        reply_message_id=getattr(reply_message, "id", None),
        max_iters_reached=max_iters_reached,
    )


def emit_agent_message(
    *,
    agent: str,
    source: str,
    message: Msg,
    call_id: str | None = None,
    last_chunk: bool | None = None,
) -> dict[str, Any] | None:
    from .runtime import get_current_scope

    scope = get_current_scope()
    return emit_event(
        "agent_message",
        category="agent",
        agent=agent,
        source=source,
        call_id=call_id,
        iteration=scope.iteration,
        step=scope.step,
        phase=scope.phase,
        last_chunk=last_chunk,
        message=_serialize_msg(message),
    )
