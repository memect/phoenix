import json
from pathlib import Path

from code_executor.document.docjson_adapter import normalize_docjson


def _docjson(text: str) -> dict:
    return {
        "pages": [
            {
                "number": 1,
                "bbox": [0, 0, 100, 100],
                "width": 100,
                "height": 100,
                "objects": [
                    {
                        "type": "markdown",
                        "bbox": [10, 10, 90, 20],
                        "text": text,
                    }
                ],
            }
        ]
    }


def _stored_docjson(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _isolate_config(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.chdir(tmp_path)


def _write_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4")


def test_import_from_pdfs_uses_ppx_dir_parser_and_configured_workers(tmp_path, monkeypatch):
    from xdev.import_data import import_from_pdfs

    _isolate_config(tmp_path, monkeypatch)
    monkeypatch.setenv("XDEV_PDF_PARSE_CONCURRENT", "4")
    pdf_dir = tmp_path / "pdfs"
    _write_pdf(pdf_dir / "a.pdf")
    _write_pdf(pdf_dir / "b.pdf")
    data_dir = tmp_path / ".xdev"
    calls = []

    def fake_parse_dir(path, *, workers, ppx_command="ppx"):
        calls.append((Path(path), workers, ppx_command))
        return {"a": _docjson("a"), "b": _docjson("b")}

    monkeypatch.setattr(
        "code_executor.document.utils.pdf_parser.parse_pdf_dir_to_docjsons",
        fake_parse_dir,
    )

    import_from_pdfs(str(pdf_dir), data_dir)

    assert calls == [(pdf_dir, 4, "ppx")]
    assert _stored_docjson(data_dir / "data" / "docjson" / "a.json") == normalize_docjson(_docjson("a"))
    assert (data_dir / "data" / "pdf" / "a.pdf").exists()


def test_add_pdfs_directory_uses_ppx_file_list_for_unskipped_files(tmp_path, monkeypatch):
    from xdev.import_data import add_pdfs

    _isolate_config(tmp_path, monkeypatch)
    monkeypatch.setenv("XDEV_PDF_PARSE_CONCURRENT", "3")
    pdf_dir = tmp_path / "pdfs"
    _write_pdf(pdf_dir / "old.pdf")
    _write_pdf(pdf_dir / "new.pdf")
    data_dir = tmp_path / ".xdev"
    existing_docjson = data_dir / "data" / "docjson" / "old.json"
    existing_docjson.parent.mkdir(parents=True)
    existing_docjson.write_text("{}", encoding="utf-8")
    calls = []

    def fake_parse_files(paths, *, workers, ppx_command="ppx"):
        calls.append(([Path(path) for path in paths], workers, ppx_command))
        return {"new": _docjson("new")}

    monkeypatch.setattr(
        "code_executor.document.utils.pdf_parser.parse_pdf_files_to_docjsons",
        fake_parse_files,
    )

    added = add_pdfs(pdf_dir, data_dir)

    assert added == ["new"]
    assert calls == [([pdf_dir / "new.pdf"], 3, "ppx")]
    assert _stored_docjson(data_dir / "data" / "docjson" / "new.json") == normalize_docjson(_docjson("new"))


def test_add_pdfs_single_file_uses_ppx_file_parser(tmp_path, monkeypatch):
    from xdev.import_data import add_pdfs

    _isolate_config(tmp_path, monkeypatch)
    pdf_path = tmp_path / "single.pdf"
    _write_pdf(pdf_path)
    data_dir = tmp_path / ".xdev"
    calls = []

    def fake_parse_file(path):
        calls.append(Path(path))
        return _docjson("single")

    monkeypatch.setattr(
        "code_executor.document.utils.pdf_parser.parse_pdf_file_to_docjson",
        fake_parse_file,
    )

    added = add_pdfs(pdf_path, data_dir)

    assert added == ["single"]
    assert calls == [pdf_path]
    assert _stored_docjson(data_dir / "data" / "docjson" / "single.json") == normalize_docjson(
        _docjson("single")
    )


def test_reparse_docs_uses_configured_ppx_workers(tmp_path, monkeypatch):
    from xdev.import_data import reparse_docs

    _isolate_config(tmp_path, monkeypatch)
    monkeypatch.setenv("XDEV_PDF_PARSE_CONCURRENT", "5")
    data_dir = tmp_path / ".xdev"
    _write_pdf(data_dir / "data" / "pdf" / "a.pdf")
    (data_dir / "data" / "docjson").mkdir(parents=True, exist_ok=True)
    calls = []

    def fake_parse_files(paths, *, workers, ppx_command="ppx"):
        calls.append(([Path(path) for path in paths], workers, ppx_command))
        return {"a": _docjson("a")}

    monkeypatch.setattr(
        "code_executor.document.utils.pdf_parser.parse_pdf_files_to_docjsons",
        fake_parse_files,
    )

    reparsed = reparse_docs(["a"], data_dir)

    assert reparsed == ["a"]
    assert calls == [([data_dir / "data" / "pdf" / "a.pdf"], 5, "ppx")]


def test_sync_parse_helper_uses_configured_ppx_workers(tmp_path, monkeypatch):
    from xdev.import_data import _parse_and_save_pdfs

    _isolate_config(tmp_path, monkeypatch)
    monkeypatch.setenv("XDEV_PDF_PARSE_CONCURRENT", "6")
    data_dir = tmp_path / ".xdev"
    (data_dir / "data" / "docjson").mkdir(parents=True)
    (data_dir / "data" / "pdf").mkdir(parents=True)
    source_pdf = tmp_path / "source" / "a.pdf"
    _write_pdf(source_pdf)
    calls = []

    def fake_parse_files(paths, *, workers, ppx_command="ppx"):
        calls.append(([Path(path) for path in paths], workers, ppx_command))
        return {"a": _docjson("a")}

    monkeypatch.setattr(
        "code_executor.document.utils.pdf_parser.parse_pdf_files_to_docjsons",
        fake_parse_files,
    )

    _parse_and_save_pdfs([("a", source_pdf)], data_dir)

    assert calls == [([source_pdf], 6, "ppx")]
    assert _stored_docjson(data_dir / "data" / "docjson" / "a.json") == normalize_docjson(_docjson("a"))
    assert (data_dir / "data" / "pdf" / "a.pdf").exists()
