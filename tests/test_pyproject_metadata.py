from pathlib import Path
import tomllib


def test_extract_agent_exposes_expected_cli_scripts_only():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    scripts = data["project"]["scripts"]

    assert scripts == {
        "tree-sitter-cli": "tree_sitter_cli:app",
        "xdev": "xdev.cli:cli",
        "xdev-config": "xdev.config_cli:cli",
        "agentic-extract": "agentic_extract.cli:cli",
        "pdf-ai-explorer": "pdf_ai_explorer.cli:app",
    }


def test_internal_dependencies_use_local_wheels():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    indexes = data["tool"]["uv"].get("index", [])
    assert all("name" not in index for index in indexes)

    sources = data["tool"]["uv"]["sources"]
    assert sources["docjson2x"] == {
        "path": "./packages/docjson2x-0.1.1-py3-none-any.whl",
    }
    assert sources["pdf-ai-explorer"] == {
        "path": "./packages/pdf_ai_explorer-0.1.1-py3-none-any.whl",
    }
