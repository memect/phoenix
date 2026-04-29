"""PDF 解析工具模块。

默认通过本机 ``ppx`` 命令将 PDF 转换为 DocJSON。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Sequence

from .apiserver import ApiServer


class ParseError(Exception):
    def __init__(
        self,
        message: str,
        api_url: str | None = None,
        command: Sequence[str] | None = None,
    ):
        super().__init__(message)
        self.api_url = api_url
        self.command = list(command) if command is not None else None


# 默认 API 参数
DEFAULT_API_PARAMS = {
    "ocr": "auto",
    "ocr-text": "baidu",
    "mode": "3",
    "textlines": "true",
    "format": "4",
    "merge-table": "true",
}


def parse_pdf_to_docjson_via_api(
    pdf_data: bytes,
    api_url: str | None = None,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """通过 legacy memect API 将 PDF 数据解析为 DocJSON。

    Args:
        pdf_data: PDF 文件的二进制数据
        api_url: API 服务器 URL
        params: API 参数，为 None 时使用默认参数

    Returns:
        解析后的 DocJSON 字典

    Raises:
        ParseError: PDF 解析失败
    """
    if api_url is None:
        raise ValueError("api_url is required")
    url = api_url
    api_params = params if params is not None else DEFAULT_API_PARAMS.copy()

    api = ApiServer(base_url=url)

    try:
        result = api.invoke(
            name="pdf2doc",
            data=pdf_data,
            params=api_params,
            output_format="json",
            async_=False,
        )

        if result is None:
            raise ParseError("API 返回空结果", api_url=url)

        return result

    except ParseError:
        raise
    except Exception as e:
        raise ParseError(str(e), api_url=url) from e


def parse_pdf_to_docjson(
    pdf_data: bytes,
    api_url: str | None = None,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """兼容旧入口；请优先使用 ``parse_pdf_to_docjson_via_api``。"""
    return parse_pdf_to_docjson_via_api(pdf_data, api_url=api_url, params=params)


def parse_pdf_file_to_docjson_via_api(
    file_path: str,
    api_url: str | None = None,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """通过 legacy memect API 将 PDF 文件解析为 DocJSON。

    Args:
        file_path: PDF 文件路径
        api_url: API 服务器 URL
        params: API 参数

    Returns:
        解析后的 DocJSON 字典

    Raises:
        FileNotFoundError: 文件不存在
        ParseError: PDF 解析失败
    """
    with open(file_path, "rb") as f:
        pdf_data = f.read()

    return parse_pdf_to_docjson_via_api(pdf_data, api_url, params)


def parse_pdf_file_to_docjson(
    file_path: str,
    api_url: str | None = None,
    params: dict[str, str] | None = None,
    *,
    ppx_command: str = "ppx",
) -> dict[str, Any]:
    """通过 PPX CLI 将单个 PDF 文件解析为 DocJSON。

    ``api_url`` / ``params`` 仅用于兼容旧调用；新代码应使用默认 PPX 路径，
    或显式调用 ``parse_pdf_file_to_docjson_via_api``。
    """
    if api_url is not None or params is not None:
        return parse_pdf_file_to_docjson_via_api(file_path, api_url=api_url, params=params)

    pdf_path = Path(file_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"不是 PDF 文件: {pdf_path}")

    with TemporaryDirectory(prefix="xdev-ppx-parse-") as tmp_dir:
        output_dir = Path(tmp_dir)
        _run_ppx_parse(pdf_path, output_dir, ppx_command=ppx_command)
        return _load_ppx_docjson(output_dir / "doc.json")


def parse_pdf_dir_to_docjsons(
    pdf_dir: str | Path,
    *,
    workers: int = 1,
    ppx_command: str = "ppx",
) -> dict[str, dict[str, Any]]:
    """通过 PPX CLI 批量解析 PDF 目录。

    Args:
        pdf_dir: PDF 目录
        workers: 同时解析多少个 PDF；1 表示顺序解析
        ppx_command: PPX 命令名或路径
    """
    pdf_dir_path = Path(pdf_dir)
    if not pdf_dir_path.exists():
        raise FileNotFoundError(f"PDF 目录不存在: {pdf_dir_path}")
    if not pdf_dir_path.is_dir():
        raise ValueError(f"不是 PDF 目录: {pdf_dir_path}")

    pdf_files = _list_pdf_files(pdf_dir_path)
    if not pdf_files:
        raise ValueError(f"PDF 目录为空: {pdf_dir_path}")

    with TemporaryDirectory(prefix="xdev-ppx-parse-") as tmp_dir:
        output_dir = Path(tmp_dir)
        _run_ppx_parse(
            pdf_dir_path,
            output_dir,
            ppx_command=ppx_command,
            workers=workers,
        )
        return _load_ppx_dir_docjsons(output_dir, pdf_files)


def parse_pdf_files_to_docjsons(
    pdf_files: Sequence[str | Path],
    *,
    workers: int = 1,
    ppx_command: str = "ppx",
) -> dict[str, dict[str, Any]]:
    """通过临时输入目录让 PPX 批量解析指定 PDF 文件列表。"""
    source_files = [Path(pdf_file) for pdf_file in pdf_files]
    if not source_files:
        return {}

    seen_names: set[str] = set()
    with TemporaryDirectory(prefix="xdev-ppx-input-") as tmp_dir:
        input_dir = Path(tmp_dir)
        for source in source_files:
            if not source.exists():
                raise FileNotFoundError(f"PDF 文件不存在: {source}")
            if not source.is_file() or source.suffix.lower() != ".pdf":
                raise ValueError(f"不是 PDF 文件: {source}")
            if source.name in seen_names:
                raise ParseError(f"批量解析中存在重名 PDF 文件: {source.name}")
            seen_names.add(source.name)
            _symlink_or_copy(source, input_dir / source.name)
        return parse_pdf_dir_to_docjsons(
            input_dir,
            workers=workers,
            ppx_command=ppx_command,
        )


def _run_ppx_parse(
    input_path: Path,
    output_dir: Path,
    *,
    ppx_command: str,
    workers: int | None = None,
) -> None:
    command = [ppx_command, "parse", str(input_path)]
    if workers is not None:
        command.extend(["--workers", str(_map_ppx_workers(workers))])
    command.extend(["--out-dir", str(output_dir)])

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ParseError(
            f"找不到 {ppx_command} 命令。请先安装 memect-ppx，并确认 {ppx_command} 在 PATH 中。",
            command=command,
        ) from exc

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        message = (
            f"ppx parse 失败: {input_path}\n"
            f"command: {' '.join(command)}\n"
            f"exit code: {result.returncode}"
        )
        if stderr:
            message += f"\nstderr: {stderr}"
        if stdout:
            message += f"\nstdout: {stdout}"
        raise ParseError(message, command=command)


def _map_ppx_workers(workers: int) -> int:
    return 0 if workers <= 1 else workers


def _load_ppx_docjson(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ParseError(f"ppx 已执行，但未找到输出文件: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ParseError(f"ppx 输出的 doc.json 无法解析: {path}") from exc


def _load_ppx_dir_docjsons(output_dir: Path, pdf_files: Sequence[Path]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for pdf_file in pdf_files:
        docjson_path = output_dir / f"{pdf_file.name}.out" / "doc.json"
        results[pdf_file.stem] = _load_ppx_docjson(docjson_path)
    return results


def _list_pdf_files(pdf_dir: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in pdf_dir.iterdir()
            if path.is_file() and path.suffix.lower() == ".pdf"
        ),
        key=lambda path: path.name,
    )


def _symlink_or_copy(source: Path, target: Path) -> None:
    try:
        target.symlink_to(source.resolve())
    except OSError:
        shutil.copy2(source, target)
