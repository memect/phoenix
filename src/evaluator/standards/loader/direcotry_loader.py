"""标准集加载器 - 负责从文件系统加载标准集"""

import json
import uuid
from typing import List, Optional, Any
from pathlib import Path

from docjson2x import DocJsonAnalyzer

from evaluator.core.models import Document, Info
from evaluator.core.evaluation_models import FullStandard
from evaluator.core.schema import Schema
from evaluator.standards.models import StandardSet, StandardSetMetadata, FullSchema, SchemaType

from .base import StandardSetLoader



class DirectoryStandardSetLoader(StandardSetLoader):
    """从文件夹结构加载标准集的实现类"""
    
    def __init__(self, path: Path|str, dataset_name: str):
        """
        初始化目录加载器
        
        Args:
            path: 标准集目录路径
            dataset_name: 标准集名称
        """
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"标准集目录不存在: {self.path}")
        self.dataset_name = dataset_name
    
    def load(self) -> StandardSet:
        """加载标准集"""
        return self.load_from_directory(self.path)
    
    async def aload(self) -> StandardSet:
        raise NotImplementedError
    
    def load_from_directory(self, path: Path) -> StandardSet:
        """从目录加载完整的标准集"""
        if not path.exists():
            raise FileNotFoundError(f"标准集目录不存在: {path}")
        
        # 获取标准集名称（目录名）
        name = path.name
        
        # 加载各个组件
        schema = self.load_schema(path)
        metadata = self.load_metadata(path, name)
        standards = self.load_standards(path, schema.type == SchemaType.LIST_OF_OBJECTS)
        
        # 更新元数据中的统计信息
        metadata.total_standards = len(standards)
        
        return StandardSet(
            name=name,
            schema=schema,
            standards=standards,
            metadata=metadata
        )
    
    def load_schema(self, path: Path) -> FullSchema:
        """加载schema文件"""
        schema_path = path / "schema.json"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema文件不存在: {schema_path}")
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_data = json.load(f)
        
        # 新格式: {"type": "object", "data": {...}}
        if 'type' in schema_data:
            return FullSchema(type=SchemaType(schema_data['type']), fields=schema_data['data'])
        else:
            return FullSchema(type=SchemaType.OBJECT, fields=schema_data)
    
    def load_metadata(self, path: Path, name: str) -> StandardSetMetadata:
        """加载或创建标准集元数据"""
        metadata_path = path / "metadata.json"
        
        if metadata_path.exists():
            # 如果存在元数据文件，则加载
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata_data = json.load(f)
            return StandardSetMetadata(**metadata_data)
        else:
            # 否则创建默认元数据
            schema_path = path / "schema.json"
            schema_type = "object"
            
            if schema_path.exists():
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema_data = json.load(f)
                    schema_type = schema_data.get('type', 'object')
            
            return StandardSetMetadata(
                name=name,
                version="1.0.0",
                description=f"从目录 {path} 自动生成的标准集",
                total_standards=0,
                train_count=0,
                test_count=0,
                schema_type=schema_type
            )
    
    def load_standards(self, path: Path, is_list_type: bool = False) -> List[FullStandard]:
        """加载标准数据"""
        standards = []
        
        # 尝试从 standard_for_evaluate 目录加载
        file = path / "standard_for_evaluate" / f"{self.dataset_name}.json"
        
        standards.extend(self._load_standards_from_file(file, path, is_list_type))
        
        return standards
    
    def _load_standards_from_file(self, file_path: Path, base_path: Path, is_list_type: bool) -> List[FullStandard]:
        """从单个JSON文件加载标准数据"""
        if not file_path.exists():
            return []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            standards_data = json.load(f)
        
        standards = []
        for std_data in standards_data:
            standard = self._create_standard_from_data(std_data, base_path, is_list_type)
            if standard:
                standards.append(standard)
        
        return standards
    
    def _load_standards_from_directory(self, standard_dir: Path, base_path: Path, is_list_type: bool) -> List[FullStandard]:
        """从标准文件目录加载所有标准"""
        standards = []
        
        for std_file in standard_dir.glob("*.json"):
            try:
                with open(std_file, 'r', encoding='utf-8') as f:
                    labels_data = json.load(f)
                
                # 从文件名推断ID
                std_id = std_file.stem
                try:
                    # 尝试将hex文件名转换回UUID格式
                    uuid_obj = uuid.UUID(hex=std_id)
                    std_id = str(uuid_obj)
                except ValueError:
                    # 如果不是有效的hex，则直接使用文件名
                    pass
                
                # 创建标准对象
                standard = self._create_standard_with_documents(
                    std_id, labels_data, base_path, is_list_type
                )
                if standard:
                    standards.append(standard)
                    
            except Exception as e:
                print(f"警告: 加载标准文件 {std_file} 时出错: {e}")
                continue
        
        return standards
    
    def _create_standard_from_data(self, std_data: dict, base_path: Path, is_list_type: bool) -> Optional[FullStandard]:
        """从数据字典创建Standard对象"""
        try:
            std_id = std_data['id']
            doc_id = std_data['document_id']
            labels = std_data['labels']
            
            # 创建带文档信息的标准
            return self._create_standard_with_documents(std_id, doc_id, labels, base_path, is_list_type)
            
        except KeyError as e:
            print(f"警告: 标准数据缺少必需字段 {e}: {std_data}")
            return None
        except Exception as e:
            print(f"警告: 创建标准时出错: {e}")
            return None
    
    def _create_standard_with_documents(self, std_id: str, doc_id: str, labels: Any, base_path: Path, is_list_type: bool) -> Optional[FullStandard]:
        """创建包含文档信息的Standard对象"""
        try:
            # 尝试加载相关文档
            document = self._load_document_for_standard(doc_id, base_path)
            
            # 创建 FullStandard 对象
            return FullStandard(
                id=std_id,
                labels=labels,
                info=Info(document=document) if document else None,
                created_at=None,
                updated_at=None
            )
                
        except Exception as e:
            print(f"警告: 为标准 {std_id} 创建文档信息时出错: {e}")
            # 创建不带文档信息的标准
            return FullStandard(id=std_id, labels=labels, info=None, created_at=None, updated_at=None)
    
    def _load_document_for_standard(self, doc_id: str, base_path: Path) -> Optional[Document]:
        """为标准加载对应的文档"""
        try:
            # 转换ID为hex格式的文件名
            hex_id = self._id_to_hex(doc_id)
            
            # 加载docjson
            docjson_path = base_path / "docjson" / f"{hex_id}.json"
            docjson = None
            if docjson_path.exists():
                with open(docjson_path, 'r', encoding='utf-8') as f:
                    docjson = json.load(f)
            
            # 加载markdown
            md_path = base_path / "md" / f"{hex_id}.md"
            md_content = ""
            if md_path.exists():
                with open(md_path, 'r', encoding='utf-8') as f:
                    md_content = f.read()
            else:
                analyzer = DocJsonAnalyzer().analyze_dict(docjson)
                md_content = analyzer.to_md(table_html=True)
            
            if docjson is not None or md_content:
                # 检查 PDF 文件是否存在
                pdf_path = base_path / "pdf" / f"{hex_id}.pdf"
                
                return Document(
                    id=doc_id,
                    docjson=docjson,
                    md=md_content,
                    pdf_path=pdf_path if pdf_path.exists() else None
                )
            
            return None
            
        except Exception as e:
            print(f"警告: 加载文档 {doc_id} 时出错: {e}")
            return None
    
    def _id_to_hex(self, std_id: str) -> str:
        """将标准ID转换为hex格式的文件名"""
        try:
            # 尝试将UUID字符串转换为hex
            uuid_obj = uuid.UUID(std_id)
            return uuid_obj.hex
        except ValueError:
            # 如果不是有效的UUID，则直接返回ID
            return std_id
