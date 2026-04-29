from agentic_extract.prompts.extract_dev import EXTRACT_DEV


def test_extract_dev_prompt_no_longer_requires_default_plan_or_docs_files():
    assert "logs/plan.md" not in EXTRACT_DEV
    assert "docs/data_issues.md" not in EXTRACT_DEV
    assert "docs/known_limitations.md" not in EXTRACT_DEV
    assert "docs/notes.md" not in EXTRACT_DEV
    assert "形成执行计划" in EXTRACT_DEV
    assert "不要假设 `docs/*.md`" in EXTRACT_DEV
