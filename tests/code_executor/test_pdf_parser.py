import json
import subprocess
from pathlib import Path

import pytest

from code_executor.document.utils.pdf_parser import (
    ParseError,
    parse_pdf_dir_to_docjsons,
    parse_pdf_file_to_docjson,
    parse_pdf_files_to_docjsons,
)


def _write_docjson(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"text": text}, ensure_ascii=False), encoding="utf-8")


def test_parse_pdf_file_uses_ppx_with_temp_output(tmp_path, monkeypatch):
    pdf_path = tmp_path / "a.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        output_dir = Path(command[command.index("--out-dir") + 1])
        _write_docjson(output_dir / "doc.json", "single")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = parse_pdf_file_to_docjson(str(pdf_path))

    assert result == {"text": "single"}
    assert commands[0][0:4] == ["ppx", "parse", str(pdf_path), "--out-dir"]
    assert len(commands[0]) == 5
    assert "--workers" not in commands[0]


def test_parse_pdf_dir_maps_default_workers_to_ppx_zero(tmp_path, monkeypatch):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "a.pdf").write_bytes(b"%PDF-1.4")
    (pdf_dir / "b.pdf").write_bytes(b"%PDF-1.4")
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        output_dir = Path(command[command.index("--out-dir") + 1])
        for pdf_file in sorted(pdf_dir.glob("*.pdf")):
            _write_docjson(output_dir / f"{pdf_file.name}.out" / "doc.json", pdf_file.stem)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = parse_pdf_dir_to_docjsons(pdf_dir, workers=1)

    assert result == {"a": {"text": "a"}, "b": {"text": "b"}}
    assert commands[0][0:3] == ["ppx", "parse", str(pdf_dir)]
    assert commands[0][3:5] == ["--workers", "0"]


def test_parse_pdf_dir_passes_custom_workers(tmp_path, monkeypatch):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "a.pdf").write_bytes(b"%PDF-1.4")
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        output_dir = Path(command[command.index("--out-dir") + 1])
        _write_docjson(output_dir / "a.pdf.out" / "doc.json", "a")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    parse_pdf_dir_to_docjsons(pdf_dir, workers=4)

    assert commands[0][3:5] == ["--workers", "4"]


def test_parse_pdf_files_uses_temp_input_directory(tmp_path, monkeypatch):
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    input_dirs = []

    def fake_run(command, **kwargs):
        input_dir = Path(command[2])
        input_dirs.append(input_dir)
        output_dir = Path(command[command.index("--out-dir") + 1])
        assert (input_dir / "source.pdf").exists()
        _write_docjson(output_dir / "source.pdf.out" / "doc.json", "source")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = parse_pdf_files_to_docjsons([pdf_path], workers=3)

    assert result == {"source": {"text": "source"}}
    assert input_dirs[0] != tmp_path


def test_parse_pdf_file_reports_missing_ppx(tmp_path, monkeypatch):
    pdf_path = tmp_path / "a.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    def fake_run(command, **kwargs):
        raise FileNotFoundError("ppx")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(ParseError, match="找不到 ppx 命令"):
        parse_pdf_file_to_docjson(str(pdf_path))


def test_parse_pdf_file_reports_ppx_failure(tmp_path, monkeypatch):
    pdf_path = tmp_path / "a.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 2, stdout="out", stderr="bad")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(ParseError, match="exit code: 2"):
        parse_pdf_file_to_docjson(str(pdf_path))


def test_parse_pdf_file_reports_missing_docjson(tmp_path, monkeypatch):
    pdf_path = tmp_path / "a.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(ParseError, match="未找到输出文件"):
        parse_pdf_file_to_docjson(str(pdf_path))


def test_parse_pdf_file_reports_invalid_docjson(tmp_path, monkeypatch):
    pdf_path = tmp_path / "a.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    def fake_run(command, **kwargs):
        output_dir = Path(command[command.index("--out-dir") + 1])
        (output_dir / "doc.json").write_text("{", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(ParseError, match="无法解析"):
        parse_pdf_file_to_docjson(str(pdf_path))
