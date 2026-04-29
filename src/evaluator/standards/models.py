"""标准集相关的数据模型"""

from enum import Enum
from typing import List, Optional, Dict, Any, Tuple, Union, TYPE_CHECKING
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field

from ..core.evaluation_models import FullStandard
from ..core.schema import Schema

if TYPE_CHECKING:
    from ..evaluators.object import ObjectEvaluator
    from ..evaluators.list_of_objects import ListOfObjectsEvaluator
    from .evaluator_factory import DatasetBoundEvaluator

class SchemaType(str, Enum):
    """数据类型"""
    OBJECT = "object"
    LIST_OF_OBJECTS = "list_of_objects"

class FullSchema(Schema):
    """增强的Schema类 - 负责标准集的管理和操作"""
    type: SchemaType = Field(..., description="数据类型: object 或 list_of_objects")

    @classmethod
    def from_dict(cls, schema_dict: dict) -> 'FullSchema':
        """从字典创建FullSchema"""
        return cls(type=SchemaType(schema_dict['type']), fields=schema_dict['data'] if 'data' in schema_dict else schema_dict)
    

class StandardSetMetadata(BaseModel):
    """标准集元数据"""
    name: str = Field(..., description="标准集名称")
    version: str = Field("1.0.0", description="版本号")
    description: str = Field("", description="描述信息")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    tags: List[str] = Field(default_factory=list, description="标签")
    total_standards: int = Field(0, description="标准总数")
    train_count: int = Field(0, description="训练集数量")
    test_count: int = Field(0, description="测试集数量")
    
    # 数据集相关配置
    schema_type: str = Field("object", description="数据类型: object 或 list_of_objects")
    
    # 扩展信息
    extra_info: Dict[str, Any] = Field(default_factory=dict, description="额外信息")


class StandardSet:
    """增强的标准集类 - 负责标准集的管理和操作"""
    
    def __init__(
        self, 
        name: str, 
        schema: FullSchema, 
        standards: List[FullStandard], 
        metadata: Optional[StandardSetMetadata] = None
    ):
        assert isinstance(schema, FullSchema), "schema 必须是 FullSchema 类型"
        self.name = name
        self.schema = schema
        self.standards = standards
        self.metadata = metadata or StandardSetMetadata(
            name=name,
            total_standards=len(standards),
            version="1.0.0",
            description="",
            train_count=0,
            test_count=0,
            schema_type=schema.type
        )
        
        # 创建索引以提高查询性能
        self._standards_index: Dict[str, FullStandard] = {std.id: std for std in standards}
    
    def get_standard(self, standard_id: str) -> Optional[FullStandard]:
        """根据ID获取单个标准"""
        return self._standards_index.get(standard_id)
    
    def get_standards_by_ids(self, ids: List[str]) -> List[FullStandard]:
        """根据ID列表获取多个标准"""
        return [std for std_id in ids if (std := self._standards_index.get(std_id))]
    
    def add_standard(self, standard: FullStandard) -> None:
        """添加标准"""
        if standard.id in self._standards_index:
            raise ValueError(f"标准 {standard.id} 已存在")
        
        self.standards.append(standard)
        self._standards_index[standard.id] = standard
        self.metadata.total_standards = len(self.standards)
        self.metadata.updated_at = datetime.now()
    
    def remove_standard(self, standard_id: str) -> bool:
        """移除标准，返回是否成功"""
        if standard_id not in self._standards_index:
            return False
        
        # 从列表中移除
        self.standards = [std for std in self.standards if std.id != standard_id]
        # 从索引中移除
        del self._standards_index[standard_id]
        
        self.metadata.total_standards = len(self.standards)
        self.metadata.updated_at = datetime.now()
        return True
    
    def split_train_test(self, test_ratio: float = 0.2) -> Tuple[List[FullStandard], List[FullStandard]]:
        """将标准集按比例分为训练集和测试集"""
        if not 0 < test_ratio < 1:
            raise ValueError("test_ratio 必须在 0 和 1 之间")
        
        total_count = len(self.standards)
        test_count = int(total_count * test_ratio)
        
        # 为了保证结果的一致性，按ID排序后再分割
        sorted_standards = sorted(self.standards, key=lambda x: x.id)
        
        train_standards = sorted_standards[test_count:]
        test_standards = sorted_standards[:test_count]
        
        return train_standards, test_standards
    
    def get_subset(self, standard_ids: List[str]) -> 'StandardSet':
        """根据ID列表创建子集"""
        subset_standards = self.get_standards_by_ids(standard_ids)
        
        subset_metadata = StandardSetMetadata(
            name=f"{self.name}_subset",
            version=self.metadata.version,
            description=f"{self.metadata.description} (subset)",
            total_standards=len(subset_standards),
            train_count=0,
            test_count=0,
            schema_type=self.metadata.schema_type,
            extra_info={
                "parent_set": self.name,
                "subset_ids": standard_ids
            }
        )
        
        return StandardSet(
            name=subset_metadata.name,
            schema=self.schema,
            standards=subset_standards,
            metadata=subset_metadata
        )
    
    def validate_standards(self) -> List[str]:
        """验证所有标准，返回错误信息列表"""
        errors = []
        
        # 检查ID唯一性
        id_counts: Dict[str, int] = {}
        for std in self.standards:
            id_counts[std.id] = id_counts.get(std.id, 0) + 1
        
        for std_id, count in id_counts.items():
            if count > 1:
                errors.append(f"重复的标准ID: {std_id} (出现 {count} 次)")
        
        # 检查标准数据是否符合schema
        for std in self.standards:
            if not self._validate_standard_against_schema(std):
                errors.append(f"标准 {std.id} 的数据不符合schema定义")
        
        return errors
    
    def _validate_standard_against_schema(self, standard: FullStandard) -> bool:
        """验证单个标准是否符合schema"""
        try:
            if not isinstance(standard.labels, dict):
                return False
            
            # 检查所有必需字段是否存在
            for field_name in self.schema.fields:
                if field_name not in standard.labels:
                    return False
            
            return True
        except Exception:
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取标准集统计信息"""
        return {
            "total_standards": len(self.standards),
            "schema_fields": list(self.schema.fields.keys()),
            "field_count": len(self.schema.fields),
            "metadata": self.metadata.dict()
        }
    
    def get_evaluator(self) -> "DatasetBoundEvaluator":
        """
        根据数据集的schema类型创建绑定了标准答案的评估器
        
        Returns:
            DatasetBoundEvaluator: 绑定了标准答案的评估器，只需要提取结果和extra_info
            
        Raises:
            ValueError: 当数据集的schema_type不支持时
        """
        # 避免循环导入，在方法内部导入
        from .evaluator_factory import DatasetEvaluator
        
        return DatasetEvaluator.from_dataset(self)
    
    def __len__(self) -> int:
        """返回标准数量"""
        return len(self.standards)
    
    def __repr__(self) -> str:
        return f"StandardSet(name='{self.name}', standards={len(self.standards)}, schema_fields={len(self.schema.fields)})"
