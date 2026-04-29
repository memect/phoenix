"""基础评估模型 - 专门用于评估的精简数据结构"""

from typing import Optional, Dict, Any, Generic, TypeVar
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field

D = TypeVar('D')


class ExceptionInfo(BaseModel):
    """异常信息"""
    error_message: str = Field("", description="错误消息")
    error_traceback: str = Field("", description="错误的完整traceback")
    exception_type: str = Field("", description="异常类型")


class RuntimeInfo(BaseModel):
    """运行时信息"""
    exception_info: Optional[ExceptionInfo] = Field(None, description="异常信息")
    stdout: str = Field("", description="标准输出")
    stderr: str = Field("", description="标准错误")


class Document(BaseModel):
    """文档模型"""
    id: str
    docjson: Any
    md: str
    pdf_path: Path | None = None
    
    model_config = {"arbitrary_types_allowed": True}
    
    def get_pdf_bytes(self) -> bytes | None:
        """按需读取 PDF 文件内容"""
        if self.pdf_path and self.pdf_path.exists():
            return self.pdf_path.read_bytes()
        return None


class Info(BaseModel):
    """标准信息"""
    document: 'Document'

class EvaluationStandard[D](BaseModel):
    """用于评估的标准数据 - 只包含评估必需的字段"""
    id: str = Field(..., description="标准ID")
    labels: D = Field(..., description="标准答案")


class EvaluationExtraction[D](BaseModel):
    """用于评估的提取结果 - 只包含评估必需的字段"""
    id: str = Field(..., description="提取结果ID")
    labels: D = Field(..., description="提取的数据")


class FullStandard[D](EvaluationStandard[D]):
    """完整标准 - 包含所有信息的扩展版本"""
    info: Optional[Info] = Field(None, description="文档信息")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    
    def to_evaluation_standard(self) -> EvaluationStandard[D]:
        """转换为评估专用的精简版本"""
        return EvaluationStandard(id=self.id, labels=self.labels)
    
    @classmethod
    def from_evaluation_standard(
        cls, 
        eval_standard: EvaluationStandard[D],
        info: Optional[Info] = None,
        **kwargs
    ) -> "FullStandard[D]":
        """从评估标准创建完整标准"""
        return cls(
            id=eval_standard.id,
            labels=eval_standard.labels,
            info=info,
            **kwargs
        )


class FullExtractedResult[D](EvaluationExtraction[D]):
    """完整提取结果 - 包含运行时信息的扩展版本"""
    success: bool = Field(True, description="提取是否成功，默认True因为失败的不应进入评估")
    runtime_info: Optional[RuntimeInfo] = Field(None, description="运行时信息")
    raw_data: Any = Field(None, description="原始提取数据")
    
    @property
    def data(self) -> Any:
        """向后兼容的 data 属性"""
        return self.raw_data

    def to_evaluation_extraction(self) -> EvaluationExtraction[D]:
        """转换为评估专用的精简版本"""
        return EvaluationExtraction(id=self.id, labels=self.labels)
    
    
    @classmethod
    def success_result(cls, data: D, stdout: str = "", stderr: str = "") -> "FullExtractedResult[D]":
        """创建成功的提取结果"""
        try:
            from .models import RuntimeInfo
            return cls(
                id="generated", 
                labels=data, 
                success=True, 
                runtime_info=RuntimeInfo(exception_info=None, stdout=stdout, stderr=stderr),
                raw_data=data
            )
        except Exception as e:
            from .models import RuntimeInfo
            return cls(
                id="generated", 
                labels=None, 
                success=True, 
                runtime_info=RuntimeInfo(exception_info=None, stdout=stdout, stderr=stderr),
                raw_data=data
            )
    
    @classmethod
    def error_result(cls, exception: Exception|None=None, stdout: str = "", stderr: str = "") -> "FullExtractedResult[D]":
        """从异常创建失败的提取结果"""
        from .models import RuntimeInfo, ExceptionInfo
        import traceback
        
        if exception is None:
            exception_info = None
        else:
            exception_info = ExceptionInfo(
                error_message=str(exception),
                error_traceback=''.join(traceback.format_exception(type(exception), exception, exception.__traceback__)),
                exception_type=type(exception).__name__
            )
        return cls(
            id="generated",
            labels=None,
            success=False,
            runtime_info=RuntimeInfo(
                exception_info=exception_info,
                stdout=stdout,
                stderr=stderr
            ),
            raw_data=None
        )
    
    def get_data_or_none(self) -> Optional[D]:
        """获取数据，如果失败则返回None（用于向后兼容）"""
        return self.labels if self.success else None
