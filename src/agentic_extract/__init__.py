"""
agentic-extract — 基于 AgentScope 的 agentic loop 提取编排层
"""

__version__ = "0.4.0"

from .api import (
    run_agentic_extract,
    run_agentic_extract_auto,
    run_agentic_extract_auto_async,
    run_agentic_extract_async,
    run_agentic_extract_request,
    run_agentic_extract_request_async,
)
from .config import AgenticExtractSettings
from .types import (
    EvaluationSummary,
    IterationResult,
    PrepareSourceConfigFile,
    PrepareSourceDataDir,
    PrepareSourceExisting,
    PrepareSourcePdfDir,
    PrepareSourceSetId,
    PrepareSpec,
    ProgressEvent,
    RunRequest,
    RunResult,
    TokenUsage,
)

__all__ = [
    "__version__",
    "run_agentic_extract",
    "run_agentic_extract_auto",
    "run_agentic_extract_auto_async",
    "run_agentic_extract_async",
    "run_agentic_extract_request",
    "run_agentic_extract_request_async",
    "AgenticExtractSettings",
    "PrepareSpec",
    "PrepareSourceExisting",
    "PrepareSourceSetId",
    "PrepareSourcePdfDir",
    "PrepareSourceDataDir",
    "PrepareSourceConfigFile",
    "RunRequest",
    "RunResult",
    "IterationResult",
    "EvaluationSummary",
    "ProgressEvent",
    "TokenUsage",
]
