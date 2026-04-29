"""Prompt modules for agentic_extract agents"""

from .supervisor import SUPERVISOR_SYSTEM_PROMPT, SUPERVISOR_FORMAT_REMINDER
from .supervisor import READONLY_LABELS_NOTICE as SUPERVISOR_READONLY_NOTICE
from .business import BUSINESS_AGENT_PREAMBLE, READONLY_LABELS_NOTICE
from .extract_dev import DEV_AGENT_PREAMBLE, EXTRACT_DEV
from .strategies import STRATEGIES
from .xdev import XDEV
from .pdf_ai_explorer import PDF_AI_EXPLORER
from .tools import DOCUMENT_API, CODE_TOOLS

__all__ = [
    "SUPERVISOR_SYSTEM_PROMPT",
    "SUPERVISOR_FORMAT_REMINDER",
    "SUPERVISOR_READONLY_NOTICE",
    "BUSINESS_AGENT_PREAMBLE",
    "READONLY_LABELS_NOTICE",
    "DEV_AGENT_PREAMBLE",
    "EXTRACT_DEV",
    "STRATEGIES",
    "XDEV",
    "PDF_AI_EXPLORER",
    "DOCUMENT_API",
    "CODE_TOOLS",
]
