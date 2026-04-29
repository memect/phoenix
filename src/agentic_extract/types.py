"""Public API models for agentic_extract."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field


ActionType = Literal["call_business", "call_dev", "evaluate", "done"]
RunStatus = Literal["completed", "failed"]
EventStatus = Literal["running", "completed", "failed"]
StepType = Literal[
    "setup",
    "probe",
    "supervisor",
    "business_agent",
    "dev_agent",
    "evaluate",
    "finalize",
]
EventType = Literal[
    "run_started",
    "phase_started",
    "phase_completed",
    "iteration_started",
    "supervisor_decided",
    "step_started",
    "step_completed",
    "heartbeat",
    "iteration_completed",
    "run_completed",
    "run_failed",
]
ReasoningEffort = Literal["low", "medium", "high"]
SupervisorMode = Literal["default", "simple"]
PrepareMode = Literal["existing", "bootstrap_if_missing"]


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


ProgressCallback = Callable[["ProgressEvent"], Any]


class TokenUsage(BaseModel):
    """Normalized token accounting."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int | None = None
    reasoning_output_tokens: int | None = None
    details_complete: bool = False


class EvaluationSummary(BaseModel):
    """Public evaluation summary for a completed iteration."""

    accuracy: float | None = None
    field_average: float | None = None
    doc_count: int | None = None
    error_count: int | None = None


class IterationResult(BaseModel):
    """Public result of a single iteration."""

    iteration: int
    action: ActionType | None = None
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime = Field(default_factory=utc_now)
    duration_sec: float = 0.0
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    evaluation: EvaluationSummary | None = None
    summary: str | None = None
    error: str | None = None


class RunResult(BaseModel):
    """Public final result returned by the Python API."""

    status: RunStatus
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime = Field(default_factory=utc_now)
    total_iteration_duration_sec: float = 0.0
    total_run_duration_sec: float = 0.0
    iteration_count: int = 0
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    iteration_token_usage: TokenUsage = Field(default_factory=TokenUsage)
    iterations: list[IterationResult] = Field(default_factory=list)
    error: str | None = None


class ProgressEvent(BaseModel):
    """Stable coarse-grained progress event."""

    type: EventType
    timestamp: datetime = Field(default_factory=utc_now)
    status: EventStatus = "running"
    iteration: int | None = None
    step: StepType | None = None
    message: str | None = None
    elapsed_step_sec: float | None = None
    elapsed_iteration_sec: float | None = None
    elapsed_total_iteration_sec: float | None = None
    elapsed_total_run_sec: float | None = None
    token_usage_delta: TokenUsage | None = None
    token_usage_total: TokenUsage = Field(default_factory=TokenUsage)
    data: dict[str, Any] = Field(default_factory=dict)


class PrepareSourceExisting(BaseModel):
    type: Literal["existing"] = "existing"


class PrepareSourceSetId(BaseModel):
    type: Literal["set-id"] = "set-id"
    set_id: str
    base_url: str = "http://localhost:8008"
    std_ids: list[str] | None = None
    limit: int | None = None


class PrepareSourcePdfDir(BaseModel):
    type: Literal["pdf-dir"] = "pdf-dir"
    pdfs_dir: str


class PrepareSourceDataDir(BaseModel):
    type: Literal["data-dir"] = "data-dir"
    data_dir: str


class PrepareSourceConfigFile(BaseModel):
    type: Literal["source-file"] = "source-file"
    source_file: str


PrepareSource = (
    PrepareSourceExisting
    | PrepareSourceSetId
    | PrepareSourcePdfDir
    | PrepareSourceDataDir
    | PrepareSourceConfigFile
)


class PrepareSpec(BaseModel):
    mode: PrepareMode = "existing"
    source: PrepareSource = Field(default_factory=PrepareSourceExisting)


class RunRequest(BaseModel):
    """Public Python API request model."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: str
    api_base: str
    api_key: str

    supervisor_model: str | None = None
    business_model: str | None = None
    dev_model: str | None = None

    workspace: str = "workspace"
    set_id: str | None = None
    std_ids: list[str] | None = None
    limit: int | None = None
    base_url: str = "http://localhost:8008"
    pdfs_dir: str | None = None
    data_dir: str | None = None
    source_file: str | None = None

    add_pdf: str | None = None
    add_pdf_force: bool = False
    sync_pdfs: bool = False

    max_iterations: int = 10
    target_accuracy: float = 0.99
    run_timeout: float | None = None
    api_timeout: float = 300.0
    max_retries: int = 0

    max_context_length: int = 128000
    compression_keep_recent: int = 10
    studio_url: str | None = None
    initial_message: str | None = None
    readonly_labels: bool = False
    reasoning_effort: ReasoningEffort | None = None
    labeling_model: str | None = None
    labeling_api_base: str | None = None
    labeling_api_key: str | None = None
    preserve_thinking: bool = False
    dry_run: bool = False
    supervisor_mode: SupervisorMode = "simple"
    use_responses_api: bool = False
    agent_max_iters: int = 25
    supervisor_max_iters: int | None = None
    business_max_iters: int | None = None
    dev_max_iters: int | None = None

    heartbeat_interval_sec: float = 10.0
    on_event: ProgressCallback | None = Field(default=None, exclude=True, repr=False)
