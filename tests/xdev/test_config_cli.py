import json
from pathlib import Path

from click.testing import CliRunner

from xdev.config_cli import cli


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_show_masks_secrets_and_displays_paths(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    agentic_path = home / ".config" / "agentic-extract" / "config.json"
    xdev_path = home / ".config" / "xdev" / "config.json"
    _write_json(
        agentic_path,
        {
            "model": "openai/GLM-5",
            "api_base": "http://glm",
            "api_key": "test-agentic-key",
            "labeling_model": "openai/deepseek-v4-flash",
            "labeling_api_base": "https://label",
            "labeling_api_key": "test-label-key",
        },
    )
    _write_json(
        xdev_path,
        {
            "base_url": "http://std.example.com",
            "concurrent": 16,
            "pdf_parse_concurrent": 7,
            "memect_api_base": "http://pdf-parser/api",
            "code_extractor": {
                "tool_setup": {
                    "extract_tool": {
                        "max_content_length": 50000,
                        "llm": {
                            "type": "openai",
                            "config": {
                                "model": "deepseek-v4-flash",
                                "api_base": "https://extract",
                                "api_key": "test-extract-key",
                            },
                        }
                    },
                    "llm_select_tool": {
                        "max_content_length": 20000,
                        "llm": {
                            "type": "openai",
                            "config": {
                                "model": "deepseek-v4-flash",
                                "api_base": "https://extract",
                                "api_key": "test-select-key",
                            },
                        }
                    },
                }
            }
        },
    )

    result = CliRunner().invoke(cli, ["--show"])

    assert result.exit_code == 0, result.output
    assert str(agentic_path) in result.output
    assert str(xdev_path) in result.output
    assert result.output.count("test...-key") >= 4
    assert "base_url: http://std.example.com" in result.output
    assert "concurrent: 16" in result.output
    assert "pdf_parse_concurrent: 7" in result.output
    assert "memect_api_base: http://pdf-parser/api" in result.output
    assert "max_content_length: 50000" in result.output
    assert "llm_select_max_content_length: 20000" in result.output
    assert "test-agentic-key" not in result.output


def test_non_interactive_requires_complete_required_groups():
    result = CliRunner().invoke(
        cli,
        [
            "--non-interactive",
            "--llm-model",
            "openai/GLM-5",
            "--llm-api-base",
            "http://glm",
            "--llm-api-key",
            "sk-agentic",
        ],
    )

    assert result.exit_code != 0
    assert "--extract-model" in result.output
    assert "--extract-api-base" in result.output
    assert "--extract-api-key" in result.output


def test_non_interactive_updates_configs_and_preserves_other_fields(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    agentic_path = home / ".config" / "agentic-extract" / "config.json"
    xdev_path = home / ".config" / "xdev" / "config.json"
    _write_json(
        agentic_path,
        {
            "model": "openai/old-main",
            "api_base": "http://old-main",
            "api_key": "sk-old-main",
            "labeling_model": "openai/old-label",
            "labeling_api_base": "http://old-label",
            "labeling_api_key": "sk-old-label",
            "target_accuracy": 0.99,
            "reasoning_effort": "high",
        },
    )
    _write_json(
        xdev_path,
        {
            "base_url": "http://std.example.com",
            "concurrent": 32,
            "pdf_parse_concurrent": 6,
            "memect_api_base": "http://pdf-parser/api",
            "code_extractor": {
                "tool_setup": {
                    "extract_tool": {
                        "max_content_length": 100000,
                        "llm": {
                            "type": "openai",
                            "config": {
                                "model": "old-extract",
                                "api_base": "http://old-extract",
                                "api_key": "sk-old-extract",
                            },
                        },
                    },
                    "llm_select_tool": {
                        "max_content_length": 50000,
                        "llm": {
                            "type": "openai",
                            "config": {
                                "model": "old-select",
                                "api_base": "http://old-select",
                                "api_key": "sk-old-select",
                            },
                        },
                    },
                }
            },
        },
    )

    result = CliRunner().invoke(
        cli,
        [
            "--non-interactive",
            "--llm-model",
            "openai/GLM-5",
            "--llm-api-base",
            "http://glm",
            "--llm-api-key",
            "sk-new-main",
            "--extract-model",
            "openai/deepseek-v4-flash",
            "--extract-api-base",
            "https://api.deepseek.com/v1",
            "--extract-api-key",
            "sk-new-extract",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "base_url: http://std.example.com" in result.output
    assert "concurrent: 32" in result.output
    assert "pdf_parse_concurrent: 6" in result.output
    assert "memect_api_base: http://pdf-parser/api" in result.output
    assert "max_content_length: 100000" in result.output
    assert "llm_select_max_content_length: 50000" in result.output

    agentic_payload = _read_json(agentic_path)
    assert agentic_payload["model"] == "openai/GLM-5"
    assert agentic_payload["api_base"] == "http://glm"
    assert agentic_payload["api_key"] == "sk-new-main"
    assert agentic_payload["labeling_model"] == "openai/old-label"
    assert agentic_payload["target_accuracy"] == 0.99
    assert agentic_payload["reasoning_effort"] == "high"

    xdev_payload = _read_json(xdev_path)
    assert xdev_payload["memect_api_base"] == "http://pdf-parser/api"
    assert xdev_payload["pdf_parse_concurrent"] == 6
    extract_tool = xdev_payload["code_extractor"]["tool_setup"]["extract_tool"]
    llm_select_tool = xdev_payload["code_extractor"]["tool_setup"]["llm_select_tool"]
    assert extract_tool["max_content_length"] == 100000
    assert llm_select_tool["max_content_length"] == 50000
    assert extract_tool["llm"]["type"] == "openai"
    assert extract_tool["llm"]["config"]["model"] == "deepseek-v4-flash"
    assert extract_tool["llm"]["config"]["api_base"] == "https://api.deepseek.com/v1"
    assert extract_tool["llm"]["config"]["api_key"] == "sk-new-extract"
    assert llm_select_tool["llm"] == extract_tool["llm"]


def test_mixed_mode_prompts_for_missing_values_and_updates_label(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    agentic_path = home / ".config" / "agentic-extract" / "config.json"
    xdev_path = home / ".config" / "xdev" / "config.json"
    _write_json(
        agentic_path,
        {
            "model": "openai/old-main",
            "api_base": "http://old-main",
            "api_key": "sk-old-main",
        },
    )
    _write_json(
        xdev_path,
        {
            "code_extractor": {
                "tool_setup": {
                    "extract_tool": {"max_content_length": 100000},
                    "llm_select_tool": {"max_content_length": 100000},
                }
            }
        },
    )

    result = CliRunner().invoke(
        cli,
        [
            "--llm-model",
            "openai/GLM-5",
            "--extract-model",
            "openai/deepseek-v4-flash",
            "--yes",
        ],
        input=(
            "http://glm\n"
            "sk-main\n"
            "https://api.deepseek.com/v1\n"
            "sk-extract\n"
            "y\n"
            "openai/label-model\n"
            "https://label\n"
            "sk-label\n"
        ),
    )

    assert result.exit_code == 0, result.output
    assert "确认写入这些配置吗？" not in result.output

    agentic_payload = _read_json(agentic_path)
    assert agentic_payload["model"] == "openai/GLM-5"
    assert agentic_payload["api_base"] == "http://glm"
    assert agentic_payload["api_key"] == "sk-main"
    assert agentic_payload["labeling_model"] == "openai/label-model"
    assert agentic_payload["labeling_api_base"] == "https://label"
    assert agentic_payload["labeling_api_key"] == "sk-label"

    xdev_payload = _read_json(xdev_path)
    assert xdev_payload["base_url"] == "http://localhost:8008"
    assert xdev_payload["concurrent"] == 16
    assert xdev_payload["pdf_parse_concurrent"] == 1
    assert xdev_payload["memect_api_base"] == "http://localhost:6111/api"
    extract_tool = xdev_payload["code_extractor"]["tool_setup"]["extract_tool"]
    llm_select_tool = xdev_payload["code_extractor"]["tool_setup"]["llm_select_tool"]
    assert extract_tool["max_content_length"] == 100000
    assert llm_select_tool["max_content_length"] == 100000
    assert extract_tool["llm"]["config"]["model"] == "deepseek-v4-flash"
    assert llm_select_tool["llm"]["config"]["model"] == "deepseek-v4-flash"


def test_non_interactive_backfills_xdev_defaults_when_missing(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    agentic_path = home / ".config" / "agentic-extract" / "config.json"
    xdev_path = home / ".config" / "xdev" / "config.json"
    _write_json(
        agentic_path,
        {
            "model": "openai/old-main",
            "api_base": "http://old-main",
            "api_key": "sk-old-main",
        },
    )
    _write_json(xdev_path, {})

    result = CliRunner().invoke(
        cli,
        [
            "--non-interactive",
            "--llm-model",
            "openai/GLM-5",
            "--llm-api-base",
            "http://glm",
            "--llm-api-key",
            "sk-new-main",
            "--extract-model",
            "openai/deepseek-v4-flash",
            "--extract-api-base",
            "https://api.deepseek.com/v1",
            "--extract-api-key",
            "sk-new-extract",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "base_url: http://localhost:8008" in result.output
    assert "concurrent: 16" in result.output
    assert "pdf_parse_concurrent: 1" in result.output
    assert "memect_api_base: http://localhost:6111/api" in result.output
    assert "max_content_length: 50000" in result.output

    xdev_payload = _read_json(xdev_path)
    assert xdev_payload["base_url"] == "http://localhost:8008"
    assert xdev_payload["concurrent"] == 16
    assert xdev_payload["pdf_parse_concurrent"] == 1
    assert xdev_payload["memect_api_base"] == "http://localhost:6111/api"

    extract_tool = xdev_payload["code_extractor"]["tool_setup"]["extract_tool"]
    llm_select_tool = xdev_payload["code_extractor"]["tool_setup"]["llm_select_tool"]
    assert extract_tool["max_content_length"] == 50000
    assert llm_select_tool["max_content_length"] == 50000
