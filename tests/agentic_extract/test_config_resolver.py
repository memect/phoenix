import json
from pathlib import Path

from agentic_extract.config import explain_config, load_config, resolve_config


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_resolve_config_uses_workspace_parent_chain_over_cwd(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    workspace = repo_root / "local" / "workspaces" / "case1"
    other_cwd = tmp_path / "external"

    _write_json(other_cwd / ".agentic-extract.json", {"model": "cwd-model"})
    _write_json(repo_root / ".agentic-extract.json", {"model": "repo-model", "api_base": "http://repo"})
    workspace.mkdir(parents=True)

    monkeypatch.chdir(other_cwd)

    config = resolve_config(str(workspace))

    assert config.model == "repo-model"
    assert config.api_base == "http://repo"


def test_load_config_applies_explicit_config_path_after_workspace_chain(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    workspace = repo_root / "workspace"
    explicit = tmp_path / "custom-config.json"

    _write_json(repo_root / ".agentic-extract.json", {"model": "repo-model", "target_accuracy": 0.91})
    _write_json(explicit, {"model": "explicit-model", "target_accuracy": 0.97})
    workspace.mkdir(parents=True)

    monkeypatch.chdir(repo_root)

    config = load_config(str(workspace), config_path=explicit)

    assert config.model == "explicit-model"
    assert config.target_accuracy == 0.97


def test_resolve_config_applies_env_then_overrides(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    monkeypatch.setenv("AE_MODEL", "env-model")
    monkeypatch.setenv("AE_MAX_ITERATIONS", "33")
    monkeypatch.setenv("AE_AGENT_MAX_ITERS", "12")
    monkeypatch.setenv("AE_DEV_MAX_ITERS", "7")

    config = resolve_config(
        str(workspace),
        overrides={"model": "override-model", "target_accuracy": 0.88},
    )

    assert config.model == "override-model"
    assert config.max_iterations == 33
    assert config.agent_max_iters == 12
    assert config.dev_max_iters == 7
    assert config.target_accuracy == 0.88


def test_explain_config_masks_secrets_and_reports_sources(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    workspace = repo_root / "workspace"
    explicit = tmp_path / "config.json"
    workspace.mkdir(parents=True)

    _write_json(repo_root / ".agentic-extract.json", {"api_key": "test-repo-key", "model": "repo-model"})
    _write_json(explicit, {"labeling_api_key": "label-secret-12345678", "api_base": "http://explicit"})

    monkeypatch.chdir(repo_root)
    monkeypatch.setenv("AE_TARGET_ACCURACY", "0.93")

    explained = explain_config(
        str(workspace),
        config_path=explicit,
        overrides={"max_iterations": 7},
    )

    resolved = explained["resolved_config"]
    assert resolved["api_key"] == "test...-key"
    assert resolved["labeling_api_key"].startswith("labe...")
    assert resolved["api_base"] == "http://explicit"
    assert resolved["target_accuracy"] == 0.93
    assert resolved["max_iterations"] == 7
    assert str(explicit.resolve()) in explained["applied_files"]
    assert "AE_TARGET_ACCURACY" in explained["applied_env"]
    assert "max_iterations" in explained["applied_override_keys"]


def test_resolve_config_can_ignore_env(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("AE_MODEL", "env-model")

    config = resolve_config(str(workspace), include_env=False)

    assert config.model != "env-model"
