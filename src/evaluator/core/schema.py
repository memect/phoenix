"""Schema 相关的数据模型"""

from typing import Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator


class FieldType(str, Enum):
    """字段类型枚举"""
    STRING = "str"
    INTEGER = "int"
    FLOAT = "float"
    BOOLEAN = "bool"
    LIST = "list"
    ARRAY = "array"  # 等同于list
    
    @classmethod
    def _missing_(cls, value: object) -> Optional["FieldType"]:
        """处理不匹配的值，支持大小写不敏感"""
        value = str(value).lower()
        for member in cls:
            if member.value.lower() == value:
                return member
        return None


class SchemaField(BaseModel):
    """Schema中的字段定义"""
    name: str = Field(..., description="字段名称")
    type: FieldType = Field(..., description="字段类型")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证字段名称"""
        if not v or not isinstance(v, str):
            raise ValueError("字段名称不能为空且必须是字符串")
        return v


class Schema(BaseModel):
    """数据模式定义"""
    fields: Dict[str, FieldType] = Field(..., description="字段定义，格式为 {'字段1': '类型1', '字段2': '类型2', ...}")
    
    @model_validator(mode='after')
    def validate_schema(self) -> 'Schema':
        """验证整个schema"""
        if not self.fields:
            raise ValueError("schema不能为空")
        return self
    
    @classmethod
    def from_dict(cls, schema_dict: Dict[str, str]) -> 'Schema':
        """从字典创建Schema"""
        fields = {}
        for field_name, field_type in schema_dict.items():
            # 尝试转换为FieldType枚举
            try:
                field_type_enum = FieldType(field_type)
                fields[field_name] = field_type_enum
            except ValueError:
                # 如果转换失败，默认为字符串类型
                fields[field_name] = FieldType.STRING
        return cls(fields=fields)
