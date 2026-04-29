"""
Evaluation Engine CLI

标准集评估命令行工具

功能：
1. run-on-docs: 输入标准集ID、文档ID列表、程序路径，运行程序并获取结果
2. evaluate: 输入标准集ID、评估类型（train/test），获取评估报告
3. list-docs: 列出标准集中的所有文档 ID

使用示例:
    # 在指定文档上运行程序
    evaluation-engine run-on-docs \\
        --set-id "xxx" \\
        --doc-ids "doc1" "doc2" \\
        --program-path examples/extract.py \\
        --base-url "http://localhost:8008"

    # 对标准集进行评估
    evaluation-engine evaluate \\
        --set-id "xxx" \\
        --program-path examples/extract.py \\
        --eval-type train \\
        --base-url "http://localhost:8008"
        
    # 列出标准集中的文档
    evaluation-engine list-docs \\
        --set-id "xxx" \\
        --base-url "http://localhost:8008"
"""

import json
import asyncio
import shutil
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

import typer
from typer import Option

from evaluator.standards.dataset_app import generate_dataset, DatasetApp
from evaluator.core.models import EvaluationResult, RecordDetailBase

logger = logging.getLogger(__name__)

app = typer.Typer(help="评估引擎命令行工具")


def read_program(program_path: str) -> str:
    """读取程序文件内容，只支持单一程序（type='all'）
    
    Args:
        program_path: 程序文件路径
        
    Returns:
        程序代码字符串
        
    Raises:
        ValueError: 如果程序文件是 type='single' 格式
        FileNotFoundError: 如果文件不存在
    """
    # 延迟导入避免循环依赖
    try:
        from simple_workflow.models import load_result_json
    except ImportError:
        # 如果 simple_workflow 不可用，直接读取文件
        with open(program_path, "r", encoding="utf-8") as f:
            return f.read()
    
    # 尝试作为 ResultJson 加载
    result_json = load_result_json(program_path)
    if result_json:
        if result_json.is_single():
            raise ValueError(
                f"程序文件 {program_path} 是 type='single' 格式（按字段分别优化），"
                "此脚本只支持单一程序。请使用 type='all' 格式的程序文件。"
            )
        programs = result_json.get_programs()
        if not isinstance(programs, str):
            raise ValueError("ResultJson type='all' 但 data 不是字符串")
        return programs
    
    # 普通文件，直接读取
    with open(program_path, "r", encoding="utf-8") as f:
        return f.read()


def download_dataset(
    set_id: str,
    base_url: str,
    download_dir: str = "/tmp/evaluate_standard_set/resources",
    max_size: int = 200,
    train_ratio: float = 2/3,
    download_files: bool = True,
    download_pdf: bool = False,
    use_cache: bool = False,
    std_ids: list[str] | None = None,
) -> str:
    """下载标准集数据，返回数据路径
    
    Args:
        set_id: 标准集 ID
        base_url: API 基础地址
        download_dir: 下载目录
        max_size: 最大文档数量
        train_ratio: 训练集比例
        download_files: 是否下载文件
        download_pdf: 是否下载 PDF 文件
        use_cache: 如果为 True，当数据集已存在时跳过下载
        std_ids: 可选的文档 ID 白名单，仅下载和使用这些文档
        
    Returns:
        数据路径
    """
    normalized_id = set_id.replace("-", "")
    data_path = str(Path(download_dir) / normalized_id)
    
    # 有白名单时不使用缓存（白名单组合可能不同）
    if use_cache and std_ids is None and Path(data_path).exists():
        train_file_alt = Path(data_path) / "standard_for_evaluate" / "train.json"
        if train_file_alt.exists():
            logger.info(f"使用缓存的数据集: {data_path}")
            return data_path
    
    Path(download_dir).mkdir(parents=True, exist_ok=True)
    
    logger.info(f"正在下载标准集: {set_id}")
    data_path = generate_dataset(
        base_url=base_url,
        set_id=set_id,
        name=normalized_id,
        base_dir=download_dir,
        download_files=download_files,
        download_pdf=download_pdf,
        max_size=max_size,
        train_ratio=train_ratio,
        std_ids=std_ids,
    )
    logger.info(f"数据集已下载到: {data_path}")
    return data_path


def extract_evaluation_data(evaluation_result: EvaluationResult) -> Dict[str, Any]:
    """从 EvaluationResult 中提取结构化评估数据
    
    Args:
        evaluation_result: 评估结果对象
        
    Returns:
        结构化的评估数据字典
    """
    field_stats = evaluation_result.field_stats
    field_count = len(field_stats)
    
    if field_count > 0:
        field_average = sum(stat.accuracy for stat in field_stats.values()) / field_count
    else:
        field_average = 0.0
    
    document_count = evaluation_result.total_records
    detail_report = evaluation_result.llm_overall_report()
    
    field_stats_dict = {}
    for field_name, stat in field_stats.items():
        field_stats_dict[field_name] = {
            "accuracy": stat.accuracy,
            "recall": stat.recall,
            "precision": stat.precision,
            "f1": stat.f1,
        }
    
    return {
        "field_count": field_count,
        "field_average": field_average,
        "document_count": document_count,
        "detail_report": detail_report,
        "field_stats": field_stats_dict,
        "overall_accuracy": evaluation_result.overall_accuracy,
        "total_correct": evaluation_result.total_correct,
    }


def format_record_detail(detail: RecordDetailBase, std_id: str) -> Dict[str, Any]:
    """格式化单个文档的评估详情
    
    Args:
        detail: 评估详情对象
        std_id: 文档 ID
        
    Returns:
        格式化的评估详情字典
    """
    return {
        "std_id": std_id,
        "field_results": detail.field_results,
        "correct_count": detail.correct_count,
        "total_fields": detail.total_fields,
        "accuracy": detail.correct_count / detail.total_fields if detail.total_fields > 0 else 0.0,
    }


@app.command("run-on-docs")
def run_on_docs(
    set_id: str = Option(..., "--set-id", help="标准集 ID"),
    doc_ids: List[str] = Option(..., "--doc-ids", help="文档 ID 列表"),
    program_path: str = Option(..., "--program-path", help="程序文件路径"),
    base_url: str = Option("http://localhost:8008", "--base-url", help="API 基础地址"),
    keys: Optional[List[str]] = Option(None, "--keys", help="评估的字段列表"),
    download_dir: str = Option(".cache", "--download-dir", help="下载/缓存目录"),
    use_cache: bool = Option(True, "--use-cache/--no-cache", help="使用缓存的数据集"),
    output_json: bool = Option(False, "--output-json", help="以 JSON 格式输出结果"),
):
    """
    在指定文档上运行程序并获取评估结果
    
    输入标准集ID、一个或多个文档ID、程序路径，得到这个程序在这些文档上的运行结果。
    """
    from .engine import EvaluationEngine
    from code_executor.tools import setup_code_tools
    
    logging.basicConfig(level=logging.INFO)
    setup_code_tools()
    
    try:
        # 下载数据集
        data_path = download_dataset(set_id, base_url, download_dir, use_cache=use_cache)
        
        # 读取程序
        program = read_program(program_path)
        
        # 创建评估引擎
        engine = EvaluationEngine.from_data_path(data_path, keys=keys)
        
        # 批量评估文档
        logger.info(f"正在评估 {len(doc_ids)} 个文档...")
        details_map = asyncio.run(engine.evaluate_program_on_std_ids(program, doc_ids, keys=keys))
        
        # 格式化结果
        results = []
        for doc_id in doc_ids:
            detail = details_map.get(doc_id)
            if detail is None:
                result = {
                    "std_id": doc_id,
                    "error": f"文档 {doc_id} 不存在于数据集中",
                }
            else:
                result = format_record_detail(detail, doc_id)
            results.append(result)
        
        # 输出结果
        if output_json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print("\n" + "=" * 60)
            print("评估结果")
            print("=" * 60)
            for result in results:
                print(f"\n文档 ID: {result['std_id']}")
                if "error" in result:
                    print(f"  错误: {result['error']}")
                else:
                    print(f"  准确率: {result['accuracy']:.2%}")
                    print(f"  正确字段数: {result['correct_count']}/{result['total_fields']}")
                    print("  字段详情:")
                    for field, is_correct in result['field_results'].items():
                        status = "✓" if is_correct else "✗"
                        print(f"    {status} {field}")
        
    finally:
        # use_cache 时不清理
        if not use_cache:
            try:
                normalized_id = set_id.replace("-", "")
                cleanup_path = Path(download_dir) / normalized_id
                if cleanup_path.exists():
                    shutil.rmtree(cleanup_path)
                    logger.info(f"已清理临时数据: {cleanup_path}")
            except Exception as e:
                logger.warning(f"清理临时数据失败: {e}")


@app.command("evaluate")
def evaluate(
    set_id: str = Option(..., "--set-id", help="标准集 ID"),
    program_path: str = Option(..., "--program-path", help="程序文件路径"),
    eval_type: str = Option("train", "--eval-type", help="评估类型 (train/test)"),
    base_url: str = Option("http://localhost:8008", "--base-url", help="API 基础地址"),
    keys: Optional[List[str]] = Option(None, "--keys", help="评估的字段列表"),
    download_dir: str = Option(".cache", "--download-dir", help="下载/缓存目录"),
    use_cache: bool = Option(True, "--use-cache/--no-cache", help="使用缓存的数据集"),
    output_json: bool = Option(False, "--output-json", help="以 JSON 格式输出结果"),
    detail: bool = Option(False, "--detail", help="输出详细评估报告"),
):
    """
    对标准集进行整体评估
    
    输入标准集ID、评估类型（train/test），获得评估总体评估报告和详细评估结果。
    """
    from .engine import EvaluationEngine
    from code_executor.tools import setup_code_tools
    
    logging.basicConfig(level=logging.INFO)
    setup_code_tools()
    
    # 验证评估类型
    if eval_type not in ["train", "test"]:
        raise typer.BadParameter(f"eval_type 必须是 'train' 或 'test'，当前值: {eval_type}")
    
    try:
        # 下载数据集
        data_path = download_dataset(set_id, base_url, download_dir, use_cache=use_cache)
        
        # 读取程序
        program = read_program(program_path)
        
        # 创建评估引擎
        engine = EvaluationEngine.from_data_path(data_path, keys=keys)
        
        # 执行评估
        logger.info(f"正在评估 ({eval_type})...")
        evaluation_result = asyncio.run(engine.evaluate_program(program, eval_type, keys=keys))
        
        # 提取评估数据
        eval_data = extract_evaluation_data(evaluation_result)
        
        # 输出结果
        if output_json:
            print(json.dumps(eval_data, ensure_ascii=False, indent=2))
        else:
            print("\n" + "=" * 60)
            print(f"评估结果 ({eval_type})")
            print("=" * 60)
            print("\n总体指标:")
            print(f"  字段数: {eval_data['field_count']}")
            print(f"  字段平均准确率: {eval_data['field_average']:.2%}")
            print(f"  文档数: {eval_data['document_count']}")
            print(f"  总体准确率: {eval_data['overall_accuracy']:.2%}")
            print(f"  正确字段总数: {eval_data['total_correct']}")
            
            print("\n字段统计:")
            for field_name, stats in eval_data['field_stats'].items():
                print(f"  {field_name}:")
                print(f"    准确率: {stats['accuracy']:.2%}")
                print(f"    召回率: {stats['recall']:.2%}")
                print(f"    精确率: {stats['precision']:.2%}")
                print(f"    F1: {stats['f1']:.2%}")
            
            if detail:
                print("\n" + "-" * 60)
                print("详细报告:")
                print("-" * 60)
                print(eval_data['detail_report'])
                
                # 生成更详细的报告
                full_report = evaluation_result.generate_report()
                print("\n" + "-" * 60)
                print("完整评估报告:")
                print("-" * 60)
                print(full_report)
        
    finally:
        # use_cache 时不清理
        if not use_cache:
            try:
                normalized_id = set_id.replace("-", "")
                cleanup_path = Path(download_dir) / normalized_id
                if cleanup_path.exists():
                    shutil.rmtree(cleanup_path)
                    logger.info(f"已清理临时数据: {cleanup_path}")
            except Exception as e:
                logger.warning(f"清理临时数据失败: {e}")


@app.command("list-docs")
def list_docs(
    set_id: str = Option(..., "--set-id", help="标准集 ID"),
    base_url: str = Option("http://localhost:8008", "--base-url", help="API 基础地址"),
):
    """
    列出标准集中的所有文档 ID
    """
    logging.basicConfig(level=logging.INFO)
    
    dataset_app = DatasetApp(base_url=base_url)
    info = dataset_app.get_info(set_id)
    
    print(f"\n标准集: {info['name']}")
    print(f"ID: {info['id']}")
    print(f"状态: {info['status']}")
    print(f"文档数量: {info['document_count']}")
    print("\n文档 ID 列表:")
    for doc_id in info['document_ids']:
        print(f"  {doc_id}")


if __name__ == "__main__":
    app()
