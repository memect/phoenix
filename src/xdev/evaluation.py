"""
xdev 评估功能
"""

import asyncio
import json
import importlib.util
from pathlib import Path

from .setup import XdevExtractionRuntime, prepare_extraction_runtime
from .api import list_doc_ids, get_docjson_path, get_pdf_path, get_label, get_schema, get_manifest
from .models import DataSourceSetId


def _setup_code_extractor_from_xdev_config() -> XdevExtractionRuntime:
    """从 xdev 配置构造提取 runtime。"""
    return prepare_extraction_runtime()


def _validate_program_document_mode(program_file: Path) -> None:
    """校验 program.py 必须使用 Document(tree) 输入模式。"""
    from code_executor.executor import detect_input_mode

    spec = importlib.util.spec_from_file_location("xdev_program_validation", str(program_file))
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载 program.py: {program_file}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "extract"):
        raise ValueError("program.py 缺少 extract() 函数")

    mode = detect_input_mode(module.extract)
    if mode != "tree":
        raise ValueError(
            "xdev 仅支持 Document 输入。请将提取入口改为 "
            "`def extract(document: Document, tool_hub: ToolHub) -> ...`，"
            "不要使用 article/list[str|Table]。"
        )


def run_evaluation(
    doc_ids: list[str] | None = None,
    data_dir: Path | str | None = None,
    workspace: Path | str | None = None,
):
    """运行评估

    Args:
        doc_ids: 要评估的文档 ID 列表，None 表示全部
        data_dir: 数据目录
        workspace: workspace 目录（包含 program.py）

    Returns:
        评估结果（ObjectEvaluationResult 或 ListOfObjectsEvaluationResult）
    """
    import sys
    import time as time_module
    from evaluator.core.evaluation_models import FullStandard, FullExtractedResult
    from evaluator.api import get_evaluator
    runtime = _setup_code_extractor_from_xdev_config()

    # 获取 schema
    schema = get_schema(data_dir)
    if schema is None:
        raise ValueError("schema 未定义")

    # 获取要评估的文档
    if doc_ids is None:
        doc_ids = list_doc_ids(data_dir)

    # 构建标准集数据
    standards = []
    eval_doc_ids = []
    for doc_id in doc_ids:
        label = get_label(doc_id, data_dir)
        if label is None:
            print(f"警告：文档 {doc_id} 没有标注，跳过")
            continue

        standards.append(
            FullStandard(id=doc_id, labels=label)
        )
        eval_doc_ids.append(doc_id)

    if not standards:
        raise ValueError("没有可用的标注数据")

    # 读取 program.py
    if workspace is None:
        workspace = Path.cwd()
    else:
        workspace = Path(workspace)

    program_file = workspace / "program.py"
    if not program_file.exists():
        raise FileNotFoundError(f"program.py 不存在: {program_file}")
    _validate_program_document_mode(program_file)

    with open(program_file, "r", encoding="utf-8") as f:
        program = f.read()

    # 读取所有 docjson 和 PDF
    from code_executor.api import batch_execute_on_docjsons

    docjsons = []
    pdf_bytes_list = []
    for doc_id in eval_doc_ids:
        docjson_path = get_docjson_path(doc_id, data_dir)
        with open(docjson_path, "r", encoding="utf-8") as f:
            docjsons.append(json.load(f))

        pdf_path = get_pdf_path(doc_id, data_dir)
        if pdf_path.exists():
            with open(pdf_path, "rb") as f:
                pdf_bytes_list.append(f.read())
        else:
            pdf_bytes_list.append(None)

    # 进度回调（使用 sys.__stdout__ 绕过 redirect_stdout 线程安全问题）
    elapsed_times: list[float] = []

    def _print(msg: str):
        sys.__stdout__.write(msg + '\n')
        sys.__stdout__.flush()

    def progress_callback(event):
        if event['event'] == 'done':
            elapsed_times.append(event['elapsed'])
            status = "ok" if event['success'] else "FAIL"
            _print(
                f"  [{event['completed']}/{event['total']}] "
                f"{event['doc_id']} {status} ({event['elapsed']:.1f}s)"
            )

    # 批量执行（async API）
    total = len(docjsons)
    print(f"正在执行提取... (共 {total} 个文档, 并发 {runtime.concurrent})")
    wall_start = time_module.time()
    results = asyncio.run(
        batch_execute_on_docjsons(
            program=program,
            docjsons=docjsons,
            concurrent=runtime.concurrent,
            pdf_bytes_list=pdf_bytes_list,
            doc_ids=eval_doc_ids,
            progress_callback=progress_callback,
            tool_hub=runtime.tool_hub,
        )
    )
    wall_elapsed = time_module.time() - wall_start
    # 恢复 stdout（防止 redirect_stdout 竞争条件导致的问题）
    sys.stdout = sys.__stdout__

    # 打印耗时统计
    if elapsed_times:
        avg_t = sum(elapsed_times) / len(elapsed_times)
        min_t = min(elapsed_times)
        max_t = max(elapsed_times)
        success_count = sum(1 for r in results if r.get('success'))
        fail_count = total - success_count
        print(
            f"提取完成: {success_count}/{total} 成功"
            + (f", {fail_count} 失败" if fail_count else "")
        )
        print(f"耗时统计: 平均 {avg_t:.1f}s, 最小 {min_t:.1f}s, 最大 {max_t:.1f}s, 总耗时 {wall_elapsed:.1f}s")

    # 构建 ExtractedResult（execute 返回 {'index':..,'success':..,'data':..}，取 data）
    extracted_results = []
    for std, result in zip(standards, results):
        data = result.get("data", result) if isinstance(result, dict) else result
        extracted_results.append(
            FullExtractedResult(id=std.id, labels=data)
        )

    # 评估
    print("正在评估...")
    parts = get_evaluator(schema.type, schema.data)
    eval_result = parts.evaluator.evaluate(
        extracted_results=extracted_results,
        standard_results=standards,
    )

    # 从 manifest 读取元数据
    from .evaluation_result import EvaluationResult
    manifest = get_manifest(data_dir)
    set_id = None
    base_url = None
    if manifest is not None and isinstance(manifest.source, DataSourceSetId):
        set_id = manifest.source.set_id
        base_url = manifest.source.base_url

    return EvaluationResult(eval_result, set_id=set_id, base_url=base_url)


def run_single_extraction(
    doc_id: str,
    data_dir: Path | str | None = None,
    workspace: Path | str | None = None,
) -> dict:
    """在单个文档上执行提取

    Args:
        doc_id: 文档 ID
        data_dir: 数据目录
        workspace: workspace 目录

    Returns:
        提取结果
    """
    runtime = _setup_code_extractor_from_xdev_config()
    from code_executor.api import execute_on_docjson

    # 读取 docjson
    docjson_path = get_docjson_path(doc_id, data_dir)
    if not docjson_path.exists():
        raise FileNotFoundError(f"文档不存在: {doc_id}")

    with open(docjson_path, "r", encoding="utf-8") as f:
        docjson = json.load(f)

    # 读取 PDF（如果存在）
    pdf_path = get_pdf_path(doc_id, data_dir)
    pdf_bytes = None
    if pdf_path.exists():
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

    # 读取 program.py
    if workspace is None:
        workspace = Path.cwd()
    else:
        workspace = Path(workspace)

    program_file = workspace / "program.py"
    if not program_file.exists():
        raise FileNotFoundError(f"program.py 不存在: {program_file}")
    _validate_program_document_mode(program_file)

    with open(program_file, "r", encoding="utf-8") as f:
        program = f.read()

    # 执行提取（async API，返回 {'index':..,'success':..,'data':..}，取 data）
    print(f"正在执行提取: {doc_id}")
    result = asyncio.run(
        execute_on_docjson(
            docjson=docjson,
            program=program,
            pdf_bytes=pdf_bytes,
            tool_hub=runtime.tool_hub,
        )
    )

    if isinstance(result, dict) and "data" in result:
        return result["data"]
    return result


def run_single_extraction_from_file(
    *,
    workspace: Path | str | None = None,
    pdf_path: Path | str | None = None,
    docjson_path: Path | str | None = None,
) -> dict:
    """在单个 PDF 或 DocJSON 文件上执行提取。

    Args:
        workspace: workspace 目录
        pdf_path: PDF 文件路径
        docjson_path: DocJSON 文件路径

    Returns:
        提取结果
    """
    if (pdf_path is None) == (docjson_path is None):
        raise ValueError("必须且只能提供 pdf_path 或 docjson_path 之一")

    runtime = _setup_code_extractor_from_xdev_config()
    from code_executor.api import execute_on_docjson

    if workspace is None:
        workspace = Path.cwd()
    else:
        workspace = Path(workspace)

    program_file = workspace / "program.py"
    if not program_file.exists():
        raise FileNotFoundError(f"program.py 不存在: {program_file}")
    _validate_program_document_mode(program_file)

    with open(program_file, "r", encoding="utf-8") as f:
        program = f.read()

    resolved_pdf_path = Path(pdf_path) if pdf_path is not None else None
    resolved_docjson_path = Path(docjson_path) if docjson_path is not None else None

    if resolved_pdf_path is not None:
        if not resolved_pdf_path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {resolved_pdf_path}")
        from code_executor.document.utils.pdf_parser import parse_pdf_file_to_docjson

        docjson = parse_pdf_file_to_docjson(str(resolved_pdf_path))
        pdf_bytes = resolved_pdf_path.read_bytes()
        input_name = str(resolved_pdf_path)
    else:
        assert resolved_docjson_path is not None
        if not resolved_docjson_path.exists():
            raise FileNotFoundError(f"DocJSON 文件不存在: {resolved_docjson_path}")
        with open(resolved_docjson_path, "r", encoding="utf-8") as f:
            docjson = json.load(f)
        pdf_bytes = None
        input_name = str(resolved_docjson_path)

    print(f"正在执行提取: {input_name}")
    result = asyncio.run(
        execute_on_docjson(
            docjson=docjson,
            program=program,
            pdf_bytes=pdf_bytes,
            tool_hub=runtime.tool_hub,
        )
    )

    if isinstance(result, dict) and "data" in result:
        return result["data"]
    return result
