from types import SimpleNamespace

from agentic_extract.evaluate import (
    format_eval_for_supervisor,
    parse_xdev_eval_output,
    run_xdev_eval,
)


def test_parse_xdev_eval_output_extracts_summary_fields():
    output = """
总体准确率: 93.00%
字段平均准确率: 96.75%
文档数: 100
错误文档数: 7
错误文档ID: a1, b2, c3
| 字段A | 93.00% |
# 评估报告
details...
"""

    snapshot = parse_xdev_eval_output(output)

    assert snapshot is not None
    assert snapshot.accuracy == 0.93
    assert snapshot.field_average == 0.9675
    assert snapshot.doc_count == 100
    assert snapshot.error_count == 7
    assert snapshot.error_doc_ids == ["a1", "b2", "c3"]
    assert snapshot.field_accuracies["字段A"] == 0.93
    assert snapshot.report_text.startswith("# 评估报告")


def test_format_eval_for_supervisor_generates_readable_summary():
    snapshot = parse_xdev_eval_output(
        """
总体准确率: 90.00%
字段平均准确率: 80.00%
文档数: 10
错误文档数: 2
错误文档ID: a1, b2
| 字段A | 100.00% |
| 字段B | 50.00% |
"""
    )

    text = format_eval_for_supervisor(snapshot)

    assert "总体准确率 90.0%" in text
    assert "字段B: 50% ⚠" in text
    assert "错误文档: a1, b2" in text


def test_run_xdev_eval_parses_subprocess_output(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "agentic_extract.evaluate.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout="总体准确率: 88.00%\n字段平均准确率: 90.00%\n文档数: 5\n",
            stderr="",
        ),
    )

    snapshot = run_xdev_eval(tmp_path)

    assert snapshot is not None
    assert snapshot.accuracy == 0.88
    assert snapshot.field_average == 0.9
    assert snapshot.doc_count == 5
