from click.testing import CliRunner

from agentic_extract.cli import cli
from agentic_extract.config import AgenticExtractSettings
from agentic_extract.types import PrepareSourceSetId, ProgressEvent, RunResult, TokenUsage


def test_cli_run_uses_public_api_and_prints_progress(monkeypatch, tmp_path):
    captured = {}

    def fake_resolve_settings(workspace, *, config_path=None, overrides=None, include_env=True):
        assert config_path == str(tmp_path / "config.json")
        assert workspace == str(tmp_path)
        assert include_env is True
        assert overrides["model"] == "demo"
        assert overrides["api_base"] == "https://example.com"
        assert overrides["api_key"] == "secret"
        assert overrides["api_timeout"] == 123.0
        assert overrides["max_iterations"] == 9
        assert overrides["agent_max_iters"] == 8
        assert overrides["supervisor_max_iters"] == 3
        assert overrides["business_max_iters"] == 4
        assert overrides["dev_max_iters"] == 10
        assert overrides["run_timeout"] == 600.0
        assert overrides["supervisor_mode"] == "simple"
        return AgenticExtractSettings(
            model="demo",
            api_base="https://example.com",
            api_key="secret",
            workspace="from-config",
            max_iterations=9,
            agent_max_iters=8,
            supervisor_max_iters=3,
            business_max_iters=4,
            dev_max_iters=10,
            run_timeout=600.0,
        )

    def fake_run_agentic_extract(settings, *, dry_run=False, on_event=None, heartbeat_interval_sec=10.0):
        captured["settings"] = settings
        captured["dry_run"] = dry_run
        captured["heartbeat_interval_sec"] = heartbeat_interval_sec

        on_event(
            ProgressEvent(
                type="iteration_started",
                iteration=1,
            )
        )
        on_event(
            ProgressEvent(
                type="heartbeat",
                iteration=1,
                step="dev_agent",
                elapsed_step_sec=1.2,
                elapsed_total_run_sec=3.4,
                token_usage_total=TokenUsage(
                    input_tokens=20,
                    output_tokens=10,
                    total_tokens=30,
                    cached_input_tokens=8,
                ),
            )
        )
        on_event(
            ProgressEvent(
                type="run_completed",
                status="completed",
                elapsed_total_run_sec=5.0,
                token_usage_total=TokenUsage(
                    input_tokens=20,
                    output_tokens=10,
                    total_tokens=30,
                ),
                data={"iteration_count": 1},
            )
        )
        return RunResult(
            status="completed",
            iteration_count=1,
            total_iteration_duration_sec=4.5,
            total_run_duration_sec=5.0,
            token_usage=TokenUsage(
                input_tokens=20,
                output_tokens=10,
                total_tokens=30,
                cached_input_tokens=8,
                reasoning_output_tokens=2,
            ),
        )

    monkeypatch.setattr("agentic_extract.config.resolve_settings", fake_resolve_settings)
    monkeypatch.setattr("agentic_extract.api.run_agentic_extract", fake_run_agentic_extract)

    runner = CliRunner()
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    result = runner.invoke(
        cli,
        [
            "run",
            "--model",
            "demo",
            "--api-base",
            "https://example.com",
            "--api-key",
            "secret",
            "--workspace",
            str(tmp_path),
            "--config",
            str(config_path),
            "--api-timeout",
            "123",
            "--max-iterations",
            "9",
            "--agent-max-iters",
            "8",
            "--supervisor-max-iters",
            "3",
            "--business-max-iters",
            "4",
            "--dev-max-iters",
            "10",
            "--run-timeout",
            "600",
            "--supervisor",
            "simple",
            "--heartbeat-interval-sec",
            "2.5",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["settings"].model == "demo"
    assert captured["settings"].api_base == "https://example.com"
    assert captured["settings"].api_key == "secret"
    assert captured["settings"].workspace == "from-config"
    assert captured["dry_run"] is False
    assert captured["heartbeat_interval_sec"] == 2.5
    assert "[budget]" in result.output
    assert "workflow_max_iterations=9" in result.output
    assert "agent_max_iters=8" in result.output
    assert "supervisor_max_iters=3" in result.output
    assert "business_max_iters=4" in result.output
    assert "dev_max_iters=10" in result.output
    assert "run_timeout=600s" in result.output
    assert "[iter 1] started" in result.output
    assert "[iter 1 | dev_agent] heartbeat" in result.output
    assert "[summary] status=completed, iterations=1" in result.output
    assert "cache=8" in result.output
    assert "reasoning=2" in result.output


def test_cli_run_budget_full_applies_preset_but_explicit_options_win(monkeypatch, tmp_path):
    captured = {}

    def fake_resolve_settings(workspace, *, config_path=None, overrides=None, include_env=True):
        _ = (config_path, include_env)
        assert workspace == str(tmp_path)
        assert overrides["max_iterations"] == 7
        assert overrides["agent_max_iters"] == 100
        assert overrides["dev_max_iters"] == 30
        captured["overrides"] = overrides
        return AgenticExtractSettings(
            model="demo",
            api_base="https://example.com",
            api_key="secret",
            workspace=str(tmp_path),
            max_iterations=7,
            agent_max_iters=100,
            dev_max_iters=30,
        )

    def fake_run_agentic_extract(settings, *, dry_run=False, on_event=None, heartbeat_interval_sec=10.0):
        _ = (dry_run, on_event, heartbeat_interval_sec)
        captured["settings"] = settings
        return RunResult(status="completed")

    monkeypatch.setattr("agentic_extract.config.resolve_settings", fake_resolve_settings)
    monkeypatch.setattr("agentic_extract.api.run_agentic_extract", fake_run_agentic_extract)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "run",
            "--model",
            "demo",
            "--api-base",
            "https://example.com",
            "--api-key",
            "secret",
            "--workspace",
            str(tmp_path),
            "--budget",
            "full",
            "--max-iterations",
            "7",
            "--dev-max-iters",
            "30",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["settings"].max_iterations == 7
    assert captured["settings"].agent_max_iters == 100
    assert captured["settings"].dev_max_iters == 30
    assert "profile=full" in result.output
    assert "workflow_max_iterations=7" in result.output
    assert "agent_max_iters=100" in result.output
    assert "dev_max_iters=30" in result.output


def test_cli_run_budget_fast_applies_preset(monkeypatch, tmp_path):
    captured = {}

    def fake_resolve_settings(workspace, *, config_path=None, overrides=None, include_env=True):
        _ = (config_path, include_env)
        assert workspace == str(tmp_path)
        assert overrides["max_iterations"] == 10
        assert overrides["agent_max_iters"] == 10
        captured["overrides"] = overrides
        return AgenticExtractSettings(
            model="demo",
            api_base="https://example.com",
            api_key="secret",
            workspace=str(tmp_path),
            max_iterations=10,
            agent_max_iters=10,
        )

    def fake_run_agentic_extract(settings, *, dry_run=False, on_event=None, heartbeat_interval_sec=10.0):
        _ = (dry_run, on_event, heartbeat_interval_sec)
        captured["settings"] = settings
        return RunResult(status="completed")

    monkeypatch.setattr("agentic_extract.config.resolve_settings", fake_resolve_settings)
    monkeypatch.setattr("agentic_extract.api.run_agentic_extract", fake_run_agentic_extract)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "run",
            "--model",
            "demo",
            "--api-base",
            "https://example.com",
            "--api-key",
            "secret",
            "--workspace",
            str(tmp_path),
            "--budget",
            "fast",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["settings"].max_iterations == 10
    assert captured["settings"].agent_max_iters == 10
    assert "profile=fast" in result.output
    assert "workflow_max_iterations=10" in result.output
    assert "agent_max_iters=10" in result.output


def test_cli_auto_uses_high_level_api_and_builds_prepare_spec(monkeypatch, tmp_path):
    captured = {}

    def fake_resolve_std_ids(std_ids, std_ids_file):
        assert std_ids == "doc-1,doc-2"
        assert std_ids_file is None
        return ["doc-1", "doc-2"]

    def fake_resolve_settings(workspace, *, config_path=None, overrides=None, include_env=True):
        assert workspace == str(tmp_path)
        assert config_path is None
        assert include_env is True
        assert overrides["workspace"] == str(tmp_path)
        assert overrides["agent_max_iters"] == 6
        assert overrides["supervisor_max_iters"] == 2
        assert overrides["business_max_iters"] == 3
        assert overrides["dev_max_iters"] == 9
        return AgenticExtractSettings(
            model="demo",
            api_base="https://example.com",
            api_key="secret",
            workspace=str(tmp_path),
            max_iterations=10,
            agent_max_iters=6,
            supervisor_max_iters=2,
            business_max_iters=3,
            dev_max_iters=9,
            run_timeout=120.0,
        )

    def fake_run_agentic_extract_auto(
        workspace,
        *,
        prepare=None,
        config_path=None,
        settings_overrides=None,
        dry_run=False,
        reset=False,
        on_event=None,
        heartbeat_interval_sec=10.0,
    ):
        captured["workspace"] = workspace
        captured["prepare"] = prepare
        captured["config_path"] = config_path
        captured["settings_overrides"] = settings_overrides
        captured["dry_run"] = dry_run
        captured["reset"] = reset
        captured["heartbeat_interval_sec"] = heartbeat_interval_sec

        on_event(
            ProgressEvent(
                type="run_completed",
                status="completed",
                elapsed_total_run_sec=5.0,
                token_usage_total=TokenUsage(total_tokens=30, input_tokens=20, output_tokens=10),
                data={"iteration_count": 1},
            )
        )
        return RunResult(
            status="completed",
            iteration_count=1,
            total_iteration_duration_sec=4.5,
            total_run_duration_sec=5.0,
            token_usage=TokenUsage(total_tokens=30, input_tokens=20, output_tokens=10),
        )

    monkeypatch.setattr("xdev.import_data.resolve_std_ids", fake_resolve_std_ids)
    monkeypatch.setattr("agentic_extract.config.resolve_settings", fake_resolve_settings)
    monkeypatch.setattr("agentic_extract.api.run_agentic_extract_auto", fake_run_agentic_extract_auto)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "auto",
            "--model",
            "demo",
            "--api-base",
            "https://example.com",
            "--api-key",
            "secret",
            "--workspace",
            str(tmp_path),
            "--set-id",
            "set-1",
            "--std-ids",
            "doc-1,doc-2",
            "--limit",
            "5",
            "--base-url",
            "https://set.example.com",
            "--agent-max-iters",
            "6",
            "--supervisor-max-iters",
            "2",
            "--business-max-iters",
            "3",
            "--dev-max-iters",
            "9",
            "--heartbeat-interval-sec",
            "2.5",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["workspace"] == str(tmp_path)
    assert isinstance(captured["prepare"].source, PrepareSourceSetId)
    assert captured["prepare"].source.set_id == "set-1"
    assert captured["prepare"].source.std_ids == ["doc-1", "doc-2"]
    assert captured["prepare"].source.limit == 5
    assert captured["prepare"].source.base_url == "https://set.example.com"
    assert captured["settings_overrides"]["model"] == "demo"
    assert captured["settings_overrides"]["api_base"] == "https://example.com"
    assert captured["settings_overrides"]["api_key"] == "secret"
    assert captured["settings_overrides"]["agent_max_iters"] == 6
    assert captured["settings_overrides"]["supervisor_max_iters"] == 2
    assert captured["settings_overrides"]["business_max_iters"] == 3
    assert captured["settings_overrides"]["dev_max_iters"] == 9
    assert captured["dry_run"] is False
    assert captured["reset"] is False
    assert captured["heartbeat_interval_sec"] == 2.5
    assert "[budget]" in result.output
    assert "agent_max_iters=6" in result.output
    assert "supervisor_max_iters=2" in result.output
    assert "business_max_iters=3" in result.output
    assert "dev_max_iters=9" in result.output
    assert "run_timeout=120s" in result.output
    assert "[run] completed" in result.output
    assert "[summary] status=completed, iterations=1" in result.output


def test_cli_run_dry_run_checks_readiness_without_normalize(monkeypatch, tmp_path):
    captured = {}

    def fake_resolve_settings(workspace, *, config_path=None, overrides=None, include_env=True):
        _ = (config_path, overrides, include_env)
        return AgenticExtractSettings(
            model="demo",
            api_base="https://example.com",
            api_key="secret",
            workspace=str(tmp_path),
        )

    def fake_ensure_workspace_ready(workspace, *, allow_normalize=True):
        captured["workspace"] = workspace
        captured["allow_normalize"] = allow_normalize

    def fake_run_agentic_extract(settings, *, dry_run=False, on_event=None, heartbeat_interval_sec=10.0):
        _ = on_event
        captured["settings"] = settings
        captured["dry_run"] = dry_run
        captured["heartbeat_interval_sec"] = heartbeat_interval_sec
        return RunResult(status="completed")

    monkeypatch.setattr("agentic_extract.config.resolve_settings", fake_resolve_settings)
    monkeypatch.setattr("agentic_extract.workspace.ensure_workspace_ready", fake_ensure_workspace_ready)
    monkeypatch.setattr("agentic_extract.api.run_agentic_extract", fake_run_agentic_extract)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "run",
            "--model",
            "demo",
            "--api-base",
            "https://example.com",
            "--api-key",
            "secret",
            "--workspace",
            str(tmp_path),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["workspace"] == str(tmp_path)
    assert captured["allow_normalize"] is False
    assert captured["dry_run"] is True
    assert captured["heartbeat_interval_sec"] == 10.0


def test_cli_run_rejects_deprecated_prepare_options():
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "run",
            "--set-id",
            "set-1",
        ],
    )

    assert result.exit_code != 0
    assert "run 已改为纯运行命令" in result.output
    assert "agentic-extract auto" in result.output


def test_cli_auto_rejects_std_ids_without_set_id():
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "auto",
            "--std-ids",
            "doc-1",
        ],
    )

    assert result.exit_code != 0
    assert "--std-ids / --std-ids-file 只能与 --set-id 一起使用" in result.output


def test_cli_help_splits_run_and_auto_options():
    runner = CliRunner()

    run_help = runner.invoke(cli, ["run", "--help"])
    auto_help = runner.invoke(cli, ["auto", "--help"])

    assert run_help.exit_code == 0, run_help.output
    assert auto_help.exit_code == 0, auto_help.output
    assert "--set-id" not in run_help.output
    assert "--pdfs-dir" not in run_help.output
    assert "--add-pdf" not in run_help.output
    assert "--budget" in run_help.output
    assert "fast=10/10" in run_help.output
    assert "--set-id" in auto_help.output
    assert "--pdfs-dir" in auto_help.output
    assert "--add-pdf" not in auto_help.output
