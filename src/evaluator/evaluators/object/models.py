from typing import Any, Dict, List, Optional, TypeAlias, Sequence
from pydantic import BaseModel, Field, SkipValidation

from ...core.models import RecordDetailBase, D, S, EvaluationResult
from ...core.evaluation_models import (
    EvaluationExtraction as ExtractedResultBase, 
    EvaluationStandard as StandardBase,
    FullExtractedResult,
    FullStandard
)
from ...core.models import RecordDetailType, FieldDetailType, BaseFieldStat
from ...core.schema import Schema

class Standard(StandardBase[dict]):
    @classmethod
    def reduce_by_keys(cls, keys: List[str]) -> List[StandardBase[dict]]:
        raise NotImplementedError("Standard.reduce_by_keys is not implemented")

ExtractedResult: TypeAlias = ExtractedResultBase[dict]

class FieldDetail(BaseModel):
    """错误详细信息"""
    name: str = Field(..., description="字段名称")
    extracted_value: Optional[Any] = Field(None, description="提取出的值")
    standard_value: Optional[Any] = Field(None, description="标准值")
    type: FieldDetailType = Field(..., description="类型: correct(正确), incorrect(值不匹配), missing(漏提), extra(多抽)")

class RecordDetail(RecordDetailBase[dict]):
    """错误详细信息 - 合并了 ExtendedRecordDetail"""
    related_field_details: List[FieldDetail] = Field(default_factory=list, description="相关字段的详细信息列表")
    # 使用 FullExtractedResult 和 FullStandard 类型
    extracted_info: SkipValidation[FullExtractedResult] = Field(..., description="提取结果")
    standared_info: SkipValidation[FullStandard] = Field(..., description="标准结果")


class FieldStats(BaseModel, BaseFieldStat):
    correct: int = Field(0, description="正确数量")
    incorrect: int = Field(0, description="错误数量")
    missing: int = Field(0, description="漏提数量（标准结果中有但提取结果中没有）")
    extra: int = Field(0, description="多抽数量（提取结果中有但标准结果中没有）")
    total: int = Field(0, description="总数量")
    # 详情列表
    details: List[FieldDetail] = Field(default_factory=list, description="详细信息列表")

    @property
    def accuracy(self) -> float:
        accuracy = self.correct / self.total if self.total > 0 else 0.0
        return accuracy

    @property
    def recall(self) -> float:
        """召回率 = 正确数 / (正确数 + 漏提数)"""
        denominator = self.correct + self.missing
        return self.correct / denominator if denominator > 0 else 0.0
    
    @property
    def precision(self) -> float:
        """精确率 = 正确数 / (正确数 + 多抽数)"""
        denominator = self.correct + self.extra
        return self.correct / denominator if denominator > 0 else 0.0
    
    @property
    def f1(self) -> float:
        """综合F1分数 = 2 * precision * recall / (precision + recall)"""
        prec = self.precision
        rec = self.recall
        return 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0


class ObjectEvaluationResult(EvaluationResult[dict]):
    """评估结果 - 合并了 ExtendedObjectEvaluationResult"""
    details: Sequence[RecordDetail] = Field(default_factory=list, description="详细信息列表")

    def get_error_details(self) -> list:
        """获取错误详细信息 - 从 ExtendedObjectEvaluationResult 合并"""
        return [d for d in self.details if d.extracted_info.success is False]

    def get_field_stats(self, field_name) -> FieldStats:
        field_details = []
        total_count = len(self.details)
        correct_count = 0
        incorrect_count = 0
        missing_count = 0
        extra_count = 0
        for detail in self.details:
            for field_detail in detail.related_field_details:
                if field_detail.name == field_name:
                    field_details.append(field_detail)
                    if field_detail.type == FieldDetailType.CORRECT:
                        correct_count += 1
                    elif field_detail.type == FieldDetailType.INCORRECT:
                        incorrect_count += 1
                    elif field_detail.type == FieldDetailType.MISSING:
                        missing_count += 1
                    else:
                        extra_count += 1

        return FieldStats(
            correct=correct_count,
            incorrect=incorrect_count,
            missing=missing_count,
            extra=extra_count,
            total=total_count,
            details=field_details
        )

    @property
    def field_stats(self) -> Dict[str, FieldStats]:
        return {field: self.get_field_stats(field) for field in self.schema_.fields}

    def has_error(self) -> bool:
        return any(record.type == RecordDetailType.ERROR for record in self.details)

    def generate_report(self, extra_keys=None):
        """生成详细的评估报告文本"""
        report_lines = []

        # --- 1. 总体摘要 ---
        report_lines.append("=" * 50)
        report_lines.append("Overall Evaluation Summary")
        report_lines.append("-" * 50)
        report_lines.append(f"Total Records: {self.total_records}")
        report_lines.append(f"Completely Correct Records: {self.total_correct}")
        if self.total_records > 0:
            record_level_accuracy = self.total_correct / self.total_records
            report_lines.append(f"Record-Level Accuracy: {record_level_accuracy:.2%}")
        report_lines.append(f"Field-Level Overall Accuracy: {self.overall_accuracy:.2%}")
        report_lines.append("")

        # --- 2. 字段级统计 ---
        report_lines.append("=" * 50)
        report_lines.append("Field-level Statistics")
        report_lines.append("-" * 50)
        
        header = f"{'Field':<20} | {'Correct':>7} | {'Incorrect':>9} | {'Missing':>7} | {'Extra':>5} | {'Accuracy':>8} | {'Precision':>9} | {'Recall':>8} | {'F1-Score':>10}"
        report_lines.append(header)
        report_lines.append("-" * len(header))

        for field_name, stats in self.field_stats.items():
            line = (
                f"{field_name:<20} | "
                f"{stats.correct:>7} | "
                f"{stats.incorrect:>9} | "
                f"{stats.missing:>7} | "
                f"{stats.extra:>5} | "
                f"{stats.accuracy:>7.2%} | "
                f"{stats.precision:>8.2%} | "
                f"{stats.recall:>7.2%} | "
                f"{stats.f1:>9.2%}"
            )
            report_lines.append(line)
        report_lines.append("")

        # --- 3. 详细错误分析 ---
        report_lines.append("=" * 50)
        report_lines.append("Detailed Error Analysis")
        report_lines.append("-" * 50)

        correct_records = [d for d in self.details if d.type == RecordDetailType.CORRECT]
        incorrect_records = [d for d in self.details if d.type == RecordDetailType.INCORRECT]

        if not incorrect_records:
            report_lines.append("No errors found. Congratulations!")
        else:
            if incorrect_records:
                report_lines.append("\n--- Incorrect Records ---")
                for detail in incorrect_records:
                    report_lines.append('')
                    report_lines.append(f"* extra info:")
                    if extra_keys is None:
                        report_lines.append('\n'.join(f"{key}: {value}" for key, value in detail.extra_info.items()))
                    else:
                        report_lines.append('\n'.join(f"{key}: {value}" for key, value in detail.extra_info.items() if key in extra_keys))
                    report_lines.append(f"id (Standard/Extracted): {detail.standared_info.id}")
                    for field_detail in detail.related_field_details:
                        if field_detail.type == FieldDetailType.INCORRECT:
                            report_lines.append(
                                f"  - [Incorrect] Field '{field_detail.name}': "
                                f"Standard: '{field_detail.standard_value}', "
                                f"Extracted: '{field_detail.extracted_value}'"
                            )
                        if field_detail.type == FieldDetailType.MISSING:
                            report_lines.append(
                                f"  - [Missing] Field '{field_detail.name}': "
                                f"Standard: '{field_detail.standard_value}', "
                                f"Extracted: -"
                            )
                        if field_detail.type == FieldDetailType.EXTRA:
                            report_lines.append(
                                f"  - [Extra] Field '{field_detail.name}': "
                                f"Standard: -, "
                                f"Extracted: '{field_detail.extracted_value}'"
                            )
                        if field_detail.type == FieldDetailType.CORRECT:
                            report_lines.append(
                                f"  - [Correct] Field '{field_detail.name}': "
                                f"Standard: '{field_detail.standard_value}', "
                                f"Extracted: '{field_detail.extracted_value}'"
                            )
        if correct_records:
            report_lines.append("\n--- Correct Records ---")
            for detail in correct_records:
                report_lines.append('')
                report_lines.append(f"* extra info:")
                if extra_keys is None:
                    report_lines.append('\n'.join(f"{key}: {value}" for key, value in detail.extra_info.items()))
                else:
                    report_lines.append('\n'.join(f"{key}: {value}" for key, value in detail.extra_info.items() if key in extra_keys))
                report_lines.append(f"id: {detail.standared_info.id}")
                for field_detail in detail.related_field_details:
                    if field_detail.type == FieldDetailType.CORRECT:
                        report_lines.append(
                            f"  - [Correct] Field '{field_detail.name}': "
                            f"Standard: '{field_detail.standard_value}', "
                            f"Extracted: '{field_detail.extracted_value}'"
                        )
                    else:
                        report_lines.append(
                            f"  - [Unknown] Field '{field_detail.name}'"
                        )
        

        return "\n".join(report_lines)

    def llm_overall_report(self) -> str:
        report_lines = []

        # --- 1. 总体摘要 ---
        report_lines.append("Overall Evaluation Summary")
        report_lines.append(f"Total Records: {self.total_records}")
        report_lines.append(f"Completely Correct Records: {self.total_correct}")
        if self.total_records > 0:
            record_level_accuracy = self.total_correct / self.total_records
            report_lines.append(f"Record-Level Accuracy: {record_level_accuracy:.2%}")
        report_lines.append(f"Field-Level Overall Accuracy: {self.overall_accuracy:.2%}")

        # --- 2. 字段级统计 ---
        report_lines.append("Field-level Statistics")
        

        for field_name, stats in self.field_stats.items():
            report_lines.append(f"{field_name}: {stats.accuracy:.2%}")

        return "\n".join(report_lines)