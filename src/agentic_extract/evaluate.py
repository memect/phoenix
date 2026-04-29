"""Evaluation helpers extracted from the legacy loop module."""

from __future__ import annotations

import subprocess
import logging
from pathlib import Path

from .state import EvaluationSnapshot

logger = logging.getLogger(__name__)


def parse_xdev_eval_output(output: str) -> EvaluationSnapshot | None:
    """Parse the textual output of `xdev eval` into an EvaluationSnapshot."""
    accuracy = 0.0
    field_average = 0.0
    doc_count = 0
    error_count = 0
    error_doc_ids: list[str] = []
    field_accuracies: dict[str, float] = {}

    for line in output.split("\n"):
        line_s = line.strip()

        if "总体准确率" in line_s and ":" in line_s:
            try:
                accuracy = float(line_s.split(":")[-1].strip().rstrip("%")) / 100.0
            except ValueError:
                pass
        elif "字段平均准确率" in line_s and ":" in line_s:
            try:
                field_average = float(line_s.split(":")[-1].strip().rstrip("%")) / 100.0
            except ValueError:
                pass
        elif (
            not line_s.endswith("**")
            and "文档数" in line_s
            and ":" in line_s
            and "错误" not in line_s
            and "字段" not in line_s
            and "正确" not in line_s
        ):
            try:
                doc_count = int(line_s.split(":")[-1].strip())
            except ValueError:
                pass
        elif "错误文档数" in line_s and ":" in line_s:
            try:
                error_count = int(line_s.split(":")[-1].strip())
            except ValueError:
                pass
        elif line_s.startswith("错误文档ID") or (
            error_count > 0
            and "," in line_s
            and len(line_s) > 30
            and all(char in "0123456789abcdef, " for char in line_s)
        ):
            ids_str = line_s.split(":", 1)[-1].strip() if ":" in line_s else line_s
            error_doc_ids = [chunk.strip() for chunk in ids_str.split(",") if chunk.strip()]
        elif line_s.startswith("|") and "%" in line_s and "---" not in line_s:
            parts = [part.strip() for part in line_s.split("|") if part.strip()]
            if len(parts) >= 2:
                field_name = parts[0]
                if field_name == "字段":
                    continue
                try:
                    field_accuracies[field_name] = float(parts[1].rstrip("%")) / 100.0
                except ValueError:
                    pass

    if accuracy == 0.0 and not field_accuracies:
        return None

    report_text = ""
    report_start = output.find("# 评估报告")
    if report_start >= 0:
        report_text = output[report_start:]

    return EvaluationSnapshot(
        accuracy=accuracy,
        field_average=field_average,
        doc_count=doc_count,
        error_count=error_count,
        error_doc_ids=error_doc_ids,
        field_accuracies=field_accuracies,
        report_text=report_text,
    )


def format_eval_for_supervisor(evaluation: EvaluationSnapshot) -> str:
    """Format evaluation output for the supervisor prompt."""
    lines = [
        f"评估结果: 总体准确率 {evaluation.accuracy:.1%}，"
        f"字段平均 {evaluation.field_average:.1%}，"
        f"文档数 {evaluation.doc_count}，错误 {evaluation.error_count} 个",
    ]
    if evaluation.field_accuracies:
        lines.append("\n字段准确率:")
        for field, acc in evaluation.field_accuracies.items():
            marker = " ⚠" if acc < 1.0 else ""
            lines.append(f"  {field}: {acc:.0%}{marker}")
    if evaluation.error_doc_ids:
        ids_str = ", ".join(evaluation.error_doc_ids[:10])
        lines.append(f"\n错误文档: {ids_str}")
    return "\n".join(lines)


def run_xdev_eval(workspace_path: Path, *, timeout: int = 300) -> EvaluationSnapshot | None:
    """Run `xdev eval` inside a workspace and parse the resulting snapshot."""
    try:
        result = subprocess.run(
            ["uv", "run", "xdev", "eval", "--data-dir", ".xdev"],
            cwd=str(workspace_path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        logger.info("xdev eval 输出:\n%s", output)
        return parse_xdev_eval_output(output)
    except Exception as exc:
        logger.warning("xdev eval 执行失败: %s", exc)
        return None
