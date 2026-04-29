from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TypeAlias, Sequence
from pydantic import BaseModel, Field, SkipValidation


from ...core.models import RecordDetailType, RecordDetailBase, D, S, EvaluationResult
from ...core.evaluation_models import (
    EvaluationExtraction as ExtractedResultBase, 
    EvaluationStandard as StandardBase,
    FullExtractedResult,
    FullStandard
)
from ...core.models import BaseFieldStat

ExtractedResult: TypeAlias = ExtractedResultBase[list[dict]]
Standard: TypeAlias = StandardBase[list[dict]]

@dataclass
class FieldStats(BaseFieldStat):
    accuracy: float = 0.0
    recall: float = 0.0
    precision: float = 0.0
    f1: float = 0.0

class MatchedObjectDetail(BaseModel):
    """匹配对象的详细信息"""
    standard_value: Any
    extracted_value: Any
    similarity_score: float
    std_list_idx: int  # 在标准列表中的索引
    ext_list_idx: int  # 在提取列表中的索引
    # mismatched_fields: List[Dict[str, Any]] = Field(default_factory=list)  # 不匹配的字段详情
    incorrect_fields: list[str]
    correct_fields: list[str]
    extra_fields: list[str]
    missing_fields: list[str]


class RecordDetail(RecordDetailBase[list[dict]]):
    """list of objects 的对比详情 - 合并了 ExtendedRecordDetail"""
    missing: List[Dict[str, Any]] = Field(default_factory=list)  # 标准中有但提取中没有的对象
    extra: List[Dict[str, Any]] = Field(default_factory=list)    # 提取中有但标准中没有的对象
    matched: List[MatchedObjectDetail] = Field(default_factory=list)  # 成功匹配的对象对
    # 使用 FullExtractedResult 和 FullStandard 类型
    extracted_info: SkipValidation[FullExtractedResult] = Field(..., description="提取结果")
    standared_info: SkipValidation[FullStandard] = Field(..., description="标准结果")


class ListOfObjectsEvaluationResult(EvaluationResult[list[dict]]):
    """列表评估结果 - 合并了 ExtendedEvaluationResult"""
    details: Sequence[RecordDetail] = Field(..., description="详细信息列表")

    def get_error_details(self) -> list:
        """获取错误详细信息 - 从 ExtendedEvaluationResult 合并"""
        return [d for d in self.details if d.extracted_info.success is False]

    def __get_field_stats(self, field: str) -> BaseFieldStat:
        all_field_stats = []
        for detail in self.details:
            if not detail.missing and not detail.extra and not detail.matched:
                detail_field_stats = FieldStats(
                    accuracy=1,
                    recall=1,
                    precision=1,
                    f1=1,
                )
            else:
                detail_missing_count = len(detail.missing) + len([m for m in detail.matched if field in m.missing_fields])
                detail_extra_count = len(detail.extra) + len([m for m in detail.matched if field in m.extra_fields])
                # todo: 这里还需要统计匹配的对象里面字段的 miss extra correct incorrect
                detail_correct_count = len([m for m in detail.matched if field in m.correct_fields])
                detail_incorrect_count = len([m for m in detail.matched if field in m.incorrect_fields])
                # 计算各种指标，确保分母不为0
                total_expected = detail_correct_count + detail_incorrect_count + detail_missing_count
                accuracy = detail_correct_count / total_expected if total_expected > 0 else 0.0
                
                recall_denominator = detail_correct_count + detail_missing_count
                recall = detail_correct_count / recall_denominator if recall_denominator > 0 else 0.0
                
                precision_denominator = detail_correct_count + detail_extra_count
                precision = detail_correct_count / precision_denominator if precision_denominator > 0 else 0.0
                
                f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
                
                detail_field_stats = FieldStats(
                    accuracy=accuracy,
                    recall=recall,
                    precision=precision,
                    f1=f1,
                )
            all_field_stats.append(detail_field_stats)
        return FieldStats(
            accuracy=sum([s.accuracy for s in all_field_stats]) / len(all_field_stats),
            recall=sum([s.recall for s in all_field_stats]) / len(all_field_stats),
            precision=sum([s.precision for s in all_field_stats]) / len(all_field_stats),
            f1=sum([s.f1 for s in all_field_stats]) / len(all_field_stats),
        )

    @property
    def field_stats(self) -> Dict[str, BaseFieldStat]:
        field_stats = {}
        for field in self.schema_.fields.keys():
            field_stats[field] = self.__get_field_stats(field)
        return field_stats

    def llm_overall_report(self) -> str:
        field_stats_str = ''
        for field, stats in self.field_stats.items():
            field_stats_str += f"{field}: {stats}\n"
        return f"""
list of objects 评估结果
overall accuracy: {self.overall_accuracy:.2%}
field stats:
{field_stats_str}
"""

    def generate_report(self, extra_keys: Optional[List[str]] = None) -> str:
        if extra_keys is None:
            extra_keys = list(self.schema_.fields.keys())
        report_lines = [
            "=" * 60,
            "List of Objects Evaluation Result",
            "-" * 60,
            f"overall accuracy: {self.overall_accuracy:.2%}",
            "-" * 60,
            f"Correct:   {self.total_correct}",
            f"Incorrect: {self.total_records - self.total_correct}",
            "=" * 60,
        ]


        def create_detail_report(details: List[RecordDetail]):
            lines = []
            for i, detail in enumerate(details):
                lines.append(f"[std id: {detail.standared_info.id}]")
                
                if detail.extra_info:
                    extra_info_str = ", ".join([
                        f"{k}: {v}" for k, v in detail.extra_info.items()
                        if k in extra_keys
                    ])
                    lines.append(f"  Context: {extra_info_str}")

                lines.append(f"  Standard: {detail.standard_value}")
                lines.append(f"  Extracted: {detail.extracted_value}")
                
                
                # 显示匹配的对象
                if detail.matched:
                    lines.append(f"  Matched Objects: {len(detail.matched)}")
                    for j, match in enumerate(detail.matched):
                        if match.similarity_score == 1.0:
                            lines.append(f"    [{j+1}] Perfect Match (similarity: {match.similarity_score:.2%})")
                        else:
                            lines.append(f"    [{j+1}] Partial Match (similarity: {match.similarity_score:.2%})")
                            # 显示不匹配的字段
                            if match.missing_fields:
                                lines.append(f"        missing fields:")
                                lines.append(str(match.missing_fields))
                            if match.extra_fields:
                                lines.append(f"        extra fields:")
                                lines.append(str(match.extra_fields))
                            if match.incorrect_fields:
                                lines.append(f"        incorrect fields:")
                                for field_name in match.incorrect_fields:
                                    lines.append(f'        - field: {field_name}')
                                    lines.append(f'          expected: {match.standard_value[field_name]}')
                                    lines.append(f'          actual: {match.extracted_value[field_name]}')
                
                # 显示缺失的对象
                if detail.missing:
                    lines.append(f"  Missing Objects: {len(detail.missing)}")
                    for j, missing_obj in enumerate(detail.missing):
                        lines.append(f"    [{j+1}] {missing_obj}")
                
                # 显示额外的对象
                if detail.extra:
                    lines.append(f"  Extra Objects: {len(detail.extra)}")
                    for j, extra_obj in enumerate(detail.extra):
                        lines.append(f"    [{j+1}] {extra_obj}")
            return lines
        
        correct_details = [detail for detail in self.details if detail.type == RecordDetailType.CORRECT]
        incorrect_details = [detail for detail in self.details if detail.type == RecordDetailType.INCORRECT]

        report_lines.append('--- Correct ---')
        report_lines.extend(create_detail_report(correct_details))
        report_lines.append('--- Incorrect ---')
        report_lines.extend(create_detail_report(incorrect_details))

        return "\n".join(report_lines)