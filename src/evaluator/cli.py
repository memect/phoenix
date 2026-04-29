"""
Evaluator CLI

评估工具命令行接口

功能：
1. compare: 比较提取结果和标准答案

使用示例:
    # 比较提取结果和标准答案
    evaluator compare \\
        --extracted result.json \\
        --standard standard.json \\
        --schema schema.json
        
    # 指定评估类型
    evaluator compare \\
        --extracted result.json \\
        --standard standard.json \\
        --schema schema.json \\
        --type list_of_objects
"""

import json
import logging
from pathlib import Path
from typing import Optional, Literal

import typer
from typer import Option

from .core.schema import Schema
from .evaluators.object import ObjectEvaluator
from .evaluators.list_of_objects import ListOfObjectsEvaluator

logger = logging.getLogger(__name__)

app = typer.Typer(help="评估工具命令行接口")


def load_json_file(file_path: str) -> dict:
    """加载 JSON 文件
    
    Args:
        file_path: JSON 文件路径
        
    Returns:
        解析后的字典
        
    Raises:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON 解析失败
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def detect_evaluation_type(extracted: dict, standard: dict) -> Literal['object', 'list_of_objects']:
    """自动检测评估类型
    
    Args:
        extracted: 提取结果
        standard: 标准答案
        
    Returns:
        评估类型: 'object' 或 'list_of_objects'
    """
    # 如果标准答案是列表，则为 list_of_objects
    if isinstance(standard, list):
        return 'list_of_objects'
    
    # 如果提取结果是列表，则为 list_of_objects
    if isinstance(extracted, list):
        return 'list_of_objects'
    
    # 默认为 object
    return 'object'


@app.command("compare")
def compare(
    extracted: str = Option(..., "--extracted", help="提取结果文件路径 (JSON)"),
    standard: str = Option(..., "--standard", help="标准答案文件路径 (JSON)"),
    schema_file: str = Option(..., "--schema", help="Schema 文件路径 (JSON)"),
    eval_type: Optional[str] = Option(None, "--type", help="评估类型 (object/list_of_objects)，不指定则自动检测"),
    output_json: bool = Option(False, "--output-json", help="以 JSON 格式输出结果"),
    detail: bool = Option(False, "--detail", help="输出详细评估报告"),
):
    """
    比较提取结果和标准答案
    
    输入提取结果文件、标准答案文件和 Schema 文件，输出评估结果。
    """
    logging.basicConfig(level=logging.INFO)
    
    try:
        # 加载文件
        extracted_data = load_json_file(extracted)
        standard_data = load_json_file(standard)
        schema_dict = load_json_file(schema_file)
        
        # 创建 Schema
        schema = Schema.from_dict(schema_dict)
        
        # 确定评估类型
        if eval_type is None:
            eval_type = detect_evaluation_type(extracted_data, standard_data)
            logger.info(f"自动检测评估类型: {eval_type}")
        
        if eval_type not in ['object', 'list_of_objects']:
            raise typer.BadParameter(f"eval_type 必须是 'object' 或 'list_of_objects'，当前值: {eval_type}")
        
        # 获取评估器
        if eval_type == 'object':
            evaluator = ObjectEvaluator(schema)
        else:
            evaluator = ListOfObjectsEvaluator(schema)
        
        # 创建评估数据 - 使用 EvaluationStandard 和 EvaluationExtraction
        from .core.evaluation_models import EvaluationStandard, EvaluationExtraction
        eval_standard = EvaluationStandard(id="compare", labels=standard_data)
        eval_extraction = EvaluationExtraction(id="compare", labels=extracted_data)
        
        # 执行评估 - evaluator.evaluate 需要列表
        result = evaluator.evaluate([eval_extraction], [eval_standard])
        
        # 构建输出数据
        output_data = {
            "overall_accuracy": result.overall_accuracy,
            "total_records": result.total_records,
            "total_correct": result.total_correct,
            "field_stats": {},
        }
        
        # 添加字段统计
        for field_name, stat in result.field_stats.items():
            output_data["field_stats"][field_name] = {
                "accuracy": stat.accuracy,
                "recall": stat.recall,
                "precision": stat.precision,
                "f1": stat.f1,
            }
        
        # 输出结果
        if output_json:
            print(json.dumps(output_data, ensure_ascii=False, indent=2))
        else:
            print("\n" + "=" * 60)
            print("评估结果")
            print("=" * 60)
            print(f"\n评估类型: {eval_type}")
            print(f"总体准确率: {output_data['overall_accuracy']:.2%}")
            print(f"总记录数: {output_data['total_records']}")
            print(f"正确记录数: {output_data['total_correct']}")
            
            if output_data["field_stats"]:
                print("\n字段统计:")
                for field_name, stats in output_data["field_stats"].items():
                    print(f"  {field_name}:")
                    print(f"    准确率: {stats['accuracy']:.2%}")
                    print(f"    召回率: {stats['recall']:.2%}")
                    print(f"    精确率: {stats['precision']:.2%}")
                    print(f"    F1: {stats['f1']:.2%}")
            
            if detail:
                print("\n" + "-" * 60)
                print("详细报告:")
                print("-" * 60)
                try:
                    report = result.generate_report()
                    print(report)
                except Exception as e:
                    logger.warning(f"生成详细报告失败: {e}")
                    # 输出基本详情
                    for i, detail_item in enumerate(result.details):
                        print(f"\n记录 {i + 1}:")
                        print(f"  类型: {detail_item.type.value}")
                        print(f"  提取值: {detail_item.extracted_value}")
                        print(f"  标准值: {detail_item.standard_value}")
    
    except FileNotFoundError as e:
        logger.error(str(e))
        raise typer.Exit(code=1)
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"评估失败: {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
