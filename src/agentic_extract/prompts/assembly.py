"""Prompt assembly logic for agentic_extract agents.

Each assemble_*_prompt function returns:
    (full_prompt: str, parts: list[PromptPart])

PromptPart records the constant name and source module for each piece,
so export-prompts can display the assembly order.
"""

from __future__ import annotations

from dataclasses import dataclass

from .supervisor import (
    SUPERVISOR_SYSTEM_PROMPT,
    SUPERVISOR_FORMAT_REMINDER,
    READONLY_LABELS_NOTICE as SUPERVISOR_READONLY_NOTICE,
)
from .supervisor_simple import (
    SUPERVISOR_SIMPLE_SYSTEM_PROMPT,
    SUPERVISOR_SIMPLE_FORMAT_REMINDER,
    READONLY_LABELS_NOTICE as SUPERVISOR_SIMPLE_READONLY_NOTICE,
)
from .business import BUSINESS_AGENT_PREAMBLE, READONLY_LABELS_NOTICE
from .extract_dev import DEV_AGENT_PREAMBLE, EXTRACT_DEV
from .strategies import STRATEGIES
from .xdev import XDEV
from .pdf_ai_explorer import PDF_AI_EXPLORER
from .tools import DOCUMENT_API, CODE_TOOLS

SEPARATOR = "\n\n---\n\n"


@dataclass
class PromptPart:
    """One piece in an assembled prompt."""

    name: str  # e.g. "SUPERVISOR_SYSTEM_PROMPT"
    source: str  # e.g. "prompts/supervisor.py"
    length: int  # character count


def _join(parts_with_text: list[tuple[str, str, str]]) -> tuple[str, list[PromptPart]]:
    """Join (name, source, text) triples into final prompt + metadata."""
    texts = []
    parts = []
    for name, source, text in parts_with_text:
        texts.append(text)
        parts.append(PromptPart(name=name, source=source, length=len(text)))
    return SEPARATOR.join(texts), parts


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------


def assemble_supervisor_prompt(
    target_accuracy: float = 0.99,
    readonly_labels: bool = False,
    simple_mode: bool = False,
) -> tuple[str, list[PromptPart]]:
    """Assemble the Supervisor system prompt."""
    target_pct = f"{target_accuracy * 100:.0f}"

    if simple_mode:
        main = SUPERVISOR_SIMPLE_SYSTEM_PROMPT.replace("{target_pct}", target_pct)
        pieces: list[tuple[str, str, str]] = [
            ("SUPERVISOR_SIMPLE_SYSTEM_PROMPT", "prompts/supervisor_simple.py", main),
        ]
        if readonly_labels:
            pieces.append(
                ("SUPERVISOR_SIMPLE_READONLY_NOTICE", "prompts/supervisor_simple.py", SUPERVISOR_SIMPLE_READONLY_NOTICE),
            )
        pieces.append(
            ("SUPERVISOR_SIMPLE_FORMAT_REMINDER", "prompts/supervisor_simple.py", SUPERVISOR_SIMPLE_FORMAT_REMINDER),
        )
    else:
        main = SUPERVISOR_SYSTEM_PROMPT.replace("{target_pct}", target_pct)
        pieces: list[tuple[str, str, str]] = [
            ("SUPERVISOR_SYSTEM_PROMPT", "prompts/supervisor.py", main),
        ]
        if readonly_labels:
            pieces.append(
                ("SUPERVISOR_READONLY_NOTICE", "prompts/supervisor.py", SUPERVISOR_READONLY_NOTICE),
            )
        pieces.append(("XDEV", "prompts/xdev.py", XDEV))
        pieces.append(
            ("SUPERVISOR_FORMAT_REMINDER", "prompts/supervisor.py", SUPERVISOR_FORMAT_REMINDER),
        )

    return _join(pieces)


# ---------------------------------------------------------------------------
# BusinessAgent
# ---------------------------------------------------------------------------


def assemble_business_prompt(
    readonly_labels: bool = False,
) -> tuple[str, list[PromptPart]]:
    """Assemble the BusinessAgent system prompt."""
    pieces: list[tuple[str, str, str]] = [
        ("BUSINESS_AGENT_PREAMBLE", "prompts/business.py", BUSINESS_AGENT_PREAMBLE),
    ]

    if readonly_labels:
        pieces.append(
            ("READONLY_LABELS_NOTICE", "prompts/business.py", READONLY_LABELS_NOTICE),
        )

    pieces.append(("XDEV", "prompts/xdev.py", XDEV))
    pieces.append(("PDF_AI_EXPLORER", "prompts/pdf_ai_explorer.py", PDF_AI_EXPLORER))

    return _join(pieces)


# ---------------------------------------------------------------------------
# DevAgent
# ---------------------------------------------------------------------------


def assemble_dev_prompt() -> tuple[str, list[PromptPart]]:
    """Assemble the DevAgent system prompt."""
    pieces: list[tuple[str, str, str]] = [
        ("DEV_AGENT_PREAMBLE", "prompts/extract_dev.py", DEV_AGENT_PREAMBLE),
        ("EXTRACT_DEV", "prompts/extract_dev.py", EXTRACT_DEV),
        ("STRATEGIES", "prompts/strategies.py", STRATEGIES),
        ("DOCUMENT_API", "prompts/tools/document_api.py", DOCUMENT_API),
        ("CODE_TOOLS", "prompts/tools/code_tools.py", CODE_TOOLS),
        ("XDEV", "prompts/xdev.py", XDEV),
        ("PDF_AI_EXPLORER", "prompts/pdf_ai_explorer.py", PDF_AI_EXPLORER),
    ]

    return _join(pieces)
