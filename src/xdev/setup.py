from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import XdevConfig, load_config


@dataclass(frozen=True)
class XdevExtractionRuntime:
    """Runtime settings shared by xdev extraction entrypoints."""

    concurrent: int
    memect_api_base: str
    tool_hub: Any | None
    config: XdevConfig


def setup() -> None:
    """Initialize legacy global code-tool policy from xdev config."""
    _configure_code_tools(load_config())


def prepare_extraction_runtime() -> XdevExtractionRuntime:
    """Load xdev config and build the ToolHub injected into code execution."""
    config = load_config()
    tool_hub = _configure_code_tools(config)
    return XdevExtractionRuntime(
        concurrent=config.concurrent,
        memect_api_base=config.memect_api_base,
        tool_hub=tool_hub,
        config=config,
    )


def _configure_code_tools(config: XdevConfig) -> Any | None:
    if config.code_extractor and config.code_extractor.tool_setup:
        from code_executor.tools import create_tool_hub, setup_code_tools, ToolsSetup

        tool_setup = ToolsSetup.model_validate(config.code_extractor.tool_setup)
        policy = setup_code_tools(tool_setup, enabled_tools=config.code_extractor.enabled_tools)
        return create_tool_hub(policy.tool_names, policy.tool_config)

    from code_executor.tools import create_tool_hub

    return create_tool_hub([], {})
