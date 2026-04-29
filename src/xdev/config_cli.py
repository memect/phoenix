"""Standalone CLI for configuring global xdev and agentic-extract settings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click

from .config import XdevConfig
from code_executor.tools.tool_setup.settings import (
    DEFAULT_EXTRACT_MAX_CONTENT_LENGTH,
    DEFAULT_LLM_SELECT_MAX_CONTENT_LENGTH,
)


@dataclass(slots=True)
class ModelEndpoint:
    """High-level model configuration used by xdev-config."""

    model: str | None = None
    api_base: str | None = None
    api_key: str | None = None

    def has_any(self) -> bool:
        return any([self.model, self.api_base, self.api_key])

    def is_complete(self) -> bool:
        return bool(self.model and self.api_base and self.api_key)


@dataclass(slots=True)
class XdevDisplaySettings:
    """Display-friendly xdev settings snapshot."""

    base_url: str
    concurrent: int
    pdf_parse_concurrent: int
    memect_api_base: str
    extract_max_content_length: int
    llm_select_max_content_length: int


def _agentic_global_config_path() -> Path:
    return Path.home() / ".config" / "agentic-extract" / "config.json"


def _xdev_global_config_path() -> Path:
    return Path.home() / ".config" / "xdev" / "config.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive branch
        raise click.ClickException(f"读取配置文件失败: {path}: {exc}") from exc


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _mask_secret(value: str | None) -> str:
    if not value:
        return "(未配置)"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _display(value: str | None) -> str:
    return value or "(未配置)"


def _parse_model_spec(model_spec: str) -> tuple[str, str]:
    model_spec = model_spec.strip()
    if "/" in model_spec:
        provider, model_name = model_spec.split("/", 1)
        return provider.lower(), model_name
    return "openai", model_spec


def _build_xdev_llm_config(model_spec: str, api_base: str, api_key: str) -> dict[str, Any]:
    provider, model_name = _parse_model_spec(model_spec)
    if provider not in {"openai", "google"}:
        raise click.ClickException(
            f"xdev 的 extract-llm 目前仅支持 openai/google provider，收到: {provider}"
        )
    return {
        "type": provider,
        "config": {
            "api_key": api_key,
            "api_base": api_base,
            "model": model_name,
        },
    }


def _extract_agentic_model(payload: dict[str, Any], *, prefix: str = "") -> ModelEndpoint:
    return ModelEndpoint(
        model=payload.get(f"{prefix}model"),
        api_base=payload.get(f"{prefix}api_base"),
        api_key=payload.get(f"{prefix}api_key"),
    )


def _extract_xdev_tool_model(payload: dict[str, Any], tool_name: str) -> ModelEndpoint:
    tool_setup = ((payload.get("code_extractor") or {}).get("tool_setup") or {})
    tool_payload = tool_setup.get(tool_name) or {}
    llm_payload = tool_payload.get("llm") or {}
    config_payload = llm_payload.get("config") or {}

    model_name = config_payload.get("model")
    provider = (llm_payload.get("type") or "openai").strip().lower()
    model_spec = None
    if model_name:
        model_spec = f"{provider}/{model_name}" if "/" not in model_name else model_name

    return ModelEndpoint(
        model=model_spec,
        api_base=config_payload.get("api_base"),
        api_key=config_payload.get("api_key"),
    )


def _extract_xdev_display_settings(payload: dict[str, Any]) -> XdevDisplaySettings:
    defaults = XdevConfig()
    tool_setup = ((payload.get("code_extractor") or {}).get("tool_setup") or {})
    extract_tool = tool_setup.get("extract_tool") or {}
    llm_select_tool = tool_setup.get("llm_select_tool") or {}

    return XdevDisplaySettings(
        base_url=payload.get("base_url") or defaults.base_url,
        concurrent=payload.get("concurrent") or defaults.concurrent,
        pdf_parse_concurrent=payload.get("pdf_parse_concurrent") or defaults.pdf_parse_concurrent,
        memect_api_base=payload.get("memect_api_base") or defaults.memect_api_base,
        extract_max_content_length=extract_tool.get("max_content_length") or DEFAULT_EXTRACT_MAX_CONTENT_LENGTH,
        llm_select_max_content_length=llm_select_tool.get("max_content_length") or DEFAULT_LLM_SELECT_MAX_CONTENT_LENGTH,
    )


def _backfill_xdev_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    defaults = XdevConfig()
    result = dict(payload)
    result["base_url"] = result.get("base_url") or defaults.base_url
    result["concurrent"] = result.get("concurrent") or defaults.concurrent
    result["pdf_parse_concurrent"] = (
        result.get("pdf_parse_concurrent") or defaults.pdf_parse_concurrent
    )
    result["memect_api_base"] = result.get("memect_api_base") or defaults.memect_api_base

    code_extractor = dict(result.get("code_extractor") or {})
    tool_setup = dict(code_extractor.get("tool_setup") or {})

    extract_tool = dict(tool_setup.get("extract_tool") or {})
    extract_tool["max_content_length"] = (
        extract_tool.get("max_content_length") or DEFAULT_EXTRACT_MAX_CONTENT_LENGTH
    )

    llm_select_tool = dict(tool_setup.get("llm_select_tool") or {})
    llm_select_tool["max_content_length"] = (
        llm_select_tool.get("max_content_length") or DEFAULT_LLM_SELECT_MAX_CONTENT_LENGTH
    )

    tool_setup["extract_tool"] = extract_tool
    tool_setup["llm_select_tool"] = llm_select_tool
    code_extractor["tool_setup"] = tool_setup
    result["code_extractor"] = code_extractor
    return result


def _merge_agentic_config(
    payload: dict[str, Any],
    *,
    llm: ModelEndpoint,
    label_llm: ModelEndpoint | None,
) -> dict[str, Any]:
    result = dict(payload)
    result.update(
        {
            "model": llm.model,
            "api_base": llm.api_base,
            "api_key": llm.api_key,
        }
    )
    if label_llm is not None:
        result.update(
            {
                "labeling_model": label_llm.model,
                "labeling_api_base": label_llm.api_base,
                "labeling_api_key": label_llm.api_key,
            }
        )
    return result


def _merge_xdev_config(payload: dict[str, Any], *, extract_llm: ModelEndpoint) -> dict[str, Any]:
    result = _backfill_xdev_defaults(payload)
    code_extractor = dict(result.get("code_extractor") or {})
    tool_setup = dict(code_extractor.get("tool_setup") or {})
    llm_payload = _build_xdev_llm_config(
        extract_llm.model or "",
        extract_llm.api_base or "",
        extract_llm.api_key or "",
    )

    extract_tool = dict(tool_setup.get("extract_tool") or {})
    extract_tool["llm"] = llm_payload

    llm_select_tool = dict(tool_setup.get("llm_select_tool") or {})
    llm_select_tool["llm"] = llm_payload

    tool_setup["extract_tool"] = extract_tool
    tool_setup["llm_select_tool"] = llm_select_tool
    code_extractor["tool_setup"] = tool_setup
    result["code_extractor"] = code_extractor
    return result


def _prompt_value(
    label: str,
    *,
    current: str | None = None,
    required: bool = True,
    hide_input: bool = False,
) -> str | None:
    prompt_label = f"{label} [回车保留现有值]" if current else label
    while True:
        value = click.prompt(
            prompt_label,
            default="",
            show_default=False,
            hide_input=hide_input,
        ).strip()
        if value:
            return value
        if current:
            return current
        if not required:
            return None
        click.echo("该项为必填，请重新输入。", err=True)


def _collect_required_model(
    title: str,
    *,
    provided: ModelEndpoint,
    current: ModelEndpoint,
) -> ModelEndpoint:
    click.echo()
    click.echo(title)
    return ModelEndpoint(
        model=provided.model or _prompt_value("  model", current=current.model),
        api_base=provided.api_base or _prompt_value("  api_base", current=current.api_base),
        api_key=provided.api_key or _prompt_value(
            "  api_key",
            current=current.api_key,
            hide_input=True,
        ),
    )


def _collect_optional_model(
    title: str,
    *,
    provided: ModelEndpoint,
    current: ModelEndpoint,
) -> ModelEndpoint:
    click.echo()
    click.echo(title)
    return ModelEndpoint(
        model=provided.model or _prompt_value("  model", current=current.model),
        api_base=provided.api_base or _prompt_value("  api_base", current=current.api_base),
        api_key=provided.api_key or _prompt_value(
            "  api_key",
            current=current.api_key,
            hide_input=True,
        ),
    )


def _validate_non_interactive_group(prefix: str, config: ModelEndpoint) -> None:
    missing: list[str] = []
    if not config.model:
        missing.append(f"--{prefix}-model")
    if not config.api_base:
        missing.append(f"--{prefix}-api-base")
    if not config.api_key:
        missing.append(f"--{prefix}-api-key")
    if missing:
        raise click.ClickException(
            "--non-interactive 模式下必须提供完整参数: " + ", ".join(missing)
        )


def _print_model_block(title: str, config: ModelEndpoint, *, note: str | None = None) -> None:
    click.echo(f"{title}:")
    click.echo(f"  model: {_display(config.model)}")
    click.echo(f"  api_base: {_display(config.api_base)}")
    click.echo(f"  api_key: {_mask_secret(config.api_key)}")
    if note:
        click.echo(f"  note: {note}")


def _print_xdev_settings_block(settings: XdevDisplaySettings) -> None:
    click.echo("xdev settings:")
    click.echo(f"  base_url: {settings.base_url}")
    click.echo(f"  concurrent: {settings.concurrent}")
    click.echo(f"  pdf_parse_concurrent: {settings.pdf_parse_concurrent}")
    click.echo(f"  memect_api_base: {settings.memect_api_base}")
    click.echo(f"  max_content_length: {settings.extract_max_content_length}")
    click.echo(f"  llm_select_max_content_length: {settings.llm_select_max_content_length}")


def _show_current_config(agentic_path: Path, xdev_path: Path) -> None:
    agentic_payload = _load_json(agentic_path)
    xdev_payload = _load_json(xdev_path)

    current_llm = _extract_agentic_model(agentic_payload)
    current_label = _extract_agentic_model(agentic_payload, prefix="labeling_")
    current_extract = _extract_xdev_tool_model(xdev_payload, "extract_tool")
    current_llm_select = _extract_xdev_tool_model(xdev_payload, "llm_select_tool")
    current_xdev_settings = _extract_xdev_display_settings(xdev_payload)

    click.echo(f"agentic-extract 全局配置: {agentic_path}")
    _print_model_block("llm", current_llm)
    if current_label.has_any():
        _print_model_block("label-llm", current_label)
    else:
        click.echo("label-llm:")
        click.echo("  (未单独配置，运行时回退到 llm)")

    click.echo()
    click.echo(f"xdev 全局配置: {xdev_path}")
    _print_xdev_settings_block(current_xdev_settings)
    _print_model_block("extract-llm (extract_tool)", current_extract)
    _print_model_block("extract-llm (llm_select_tool)", current_llm_select)


def _print_write_summary(
    *,
    agentic_path: Path,
    xdev_path: Path,
    xdev_settings: XdevDisplaySettings,
    llm: ModelEndpoint,
    extract_llm: ModelEndpoint,
    label_llm: ModelEndpoint | None,
    current_label_llm: ModelEndpoint,
) -> None:
    click.echo()
    click.echo("将写入以下全局配置：")
    click.echo(f"- agentic-extract: {agentic_path}")
    _print_model_block("  llm", llm)
    if label_llm is not None:
        _print_model_block("  label-llm", label_llm)
    elif current_label_llm.has_any():
        _print_model_block("  label-llm", current_label_llm, note="保留现有配置")
    else:
        click.echo("  label-llm:")
        click.echo("    (未单独配置，运行时回退到 llm)")

    click.echo(f"- xdev: {xdev_path}")
    _print_xdev_settings_block(xdev_settings)
    _print_model_block("  extract-llm", extract_llm, note="同时写入 extract_tool 和 llm_select_tool")


@click.command()
@click.option("--llm-model", help="agentic-extract 主 llm 模型，如 openai/GLM-5")
@click.option("--llm-api-base", help="agentic-extract 主 llm 的 API Base")
@click.option("--llm-api-key", help="agentic-extract 主 llm 的 API Key")
@click.option("--extract-model", help="xdev extract-llm 模型，如 openai/deepseek-v4-flash")
@click.option("--extract-api-base", help="xdev extract-llm 的 API Base")
@click.option("--extract-api-key", help="xdev extract-llm 的 API Key")
@click.option("--label-model", help="可选的独立 label-llm 模型")
@click.option("--label-api-base", help="可选的独立 label-llm API Base")
@click.option("--label-api-key", help="可选的独立 label-llm API Key")
@click.option("--show", is_flag=True, help="显示当前全局配置并退出")
@click.option("--yes", is_flag=True, help="跳过最终确认")
@click.option("--non-interactive", is_flag=True, help="不进入交互，缺少必填参数时直接报错")
def cli(
    llm_model: str | None,
    llm_api_base: str | None,
    llm_api_key: str | None,
    extract_model: str | None,
    extract_api_base: str | None,
    extract_api_key: str | None,
    label_model: str | None,
    label_api_base: str | None,
    label_api_key: str | None,
    show: bool,
    yes: bool,
    non_interactive: bool,
) -> None:
    """配置全局 agentic-extract 与 xdev 模型设置。"""

    agentic_path = _agentic_global_config_path()
    xdev_path = _xdev_global_config_path()

    provided_llm = ModelEndpoint(llm_model, llm_api_base, llm_api_key)
    provided_extract = ModelEndpoint(extract_model, extract_api_base, extract_api_key)
    provided_label = ModelEndpoint(label_model, label_api_base, label_api_key)

    if show:
        if provided_llm.has_any() or provided_extract.has_any() or provided_label.has_any() or yes or non_interactive:
            raise click.ClickException("--show 不能与写入参数一起使用")
        _show_current_config(agentic_path, xdev_path)
        return

    agentic_payload = _load_json(agentic_path)
    xdev_payload = _load_json(xdev_path)

    current_llm = _extract_agentic_model(agentic_payload)
    current_label = _extract_agentic_model(agentic_payload, prefix="labeling_")
    current_extract = _extract_xdev_tool_model(xdev_payload, "extract_tool")
    if non_interactive:
        _validate_non_interactive_group("llm", provided_llm)
        _validate_non_interactive_group("extract", provided_extract)
        if provided_label.has_any():
            _validate_non_interactive_group("label", provided_label)
        final_llm = provided_llm
        final_extract = provided_extract
        final_label = provided_label if provided_label.has_any() else None
    else:
        final_llm = _collect_required_model("配置 llm（agentic-extract）", provided=provided_llm, current=current_llm)
        final_extract = _collect_required_model(
            "配置 extract-llm（xdev 的 extract / llm_select 共用）",
            provided=provided_extract,
            current=current_extract,
        )

        if provided_label.has_any():
            final_label = _collect_optional_model(
                "配置 label-llm（可选）",
                provided=provided_label,
                current=current_label,
            )
        else:
            label_prompt = "更新独立的 label-llm 吗？" if current_label.has_any() else "配置独立的 label-llm 吗？"
            if click.confirm(label_prompt, default=False):
                final_label = _collect_optional_model(
                    "配置 label-llm（可选）",
                    provided=provided_label,
                    current=current_label,
                )
            else:
                final_label = None

    updated_agentic = _merge_agentic_config(agentic_payload, llm=final_llm, label_llm=final_label)
    updated_xdev = _merge_xdev_config(xdev_payload, extract_llm=final_extract)
    final_xdev_settings = _extract_xdev_display_settings(updated_xdev)

    _print_write_summary(
        agentic_path=agentic_path,
        xdev_path=xdev_path,
        xdev_settings=final_xdev_settings,
        llm=final_llm,
        extract_llm=final_extract,
        label_llm=final_label,
        current_label_llm=current_label,
    )

    if not non_interactive and not yes:
        if not click.confirm("确认写入这些配置吗？", default=True):
            click.echo("已取消，未写入任何配置。")
            return

    _write_json(agentic_path, updated_agentic)
    _write_json(xdev_path, updated_xdev)

    click.echo()
    click.echo(f"已写入 agentic-extract 全局配置: {agentic_path}")
    click.echo(f"已写入 xdev 全局配置: {xdev_path}")
    click.echo("xdev 的 extract_tool 与 llm_select_tool 已同步为 extract-llm。")
