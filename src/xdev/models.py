"""
xdev 数据模型
"""

from typing import Literal
from pathlib import Path
from pydantic import BaseModel


class DataSourceSetId(BaseModel):
    """远程标准集数据源"""
    type: Literal["set-id"] = "set-id"
    set_id: str
    base_url: str
    std_ids: list[str] | None = None


class DataSourcePdfs(BaseModel):
    """本地 PDF 目录数据源"""
    type: Literal["pdfs"] = "pdfs"
    pdf_dir: str


class DataSourceDataDir(BaseModel):
    """另一个 data-dir 数据源"""
    type: Literal["data-dir"] = "data-dir"
    path: str


DataSource = DataSourceSetId | DataSourcePdfs | DataSourceDataDir


class Manifest(BaseModel):
    """数据源元信息"""
    source: DataSource
    imported_at: str  # ISO 8601 timestamp
    doc_count: int
    migration_info: dict | None = None  # 迁移元信息（可选）


class SchemaField(BaseModel):
    """Schema 字段定义"""
    type: Literal["str", "int", "float", "bool", "list"]


class Schema(BaseModel):
    """Schema 定义"""
    type: Literal["object", "list_of_objects"]
    data: dict[str, str]  # field_name -> type_name
