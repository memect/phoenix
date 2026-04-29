"""标准集管理器 - 负责标准集的管理和操作"""

from typing import Dict, List, Optional, Any, TYPE_CHECKING
from pathlib import Path

from ..core.schema import Schema
from .models import StandardSet, StandardSetMetadata
from .loader import StandardSetLoader, DirectoryStandardSetLoader


class StandardSetManager:
    """标准集管理器 - 统一管理多个标准集"""
    
    def __init__(self):
        """
        初始化标准集管理器
        """
        self._loaded_sets: Dict[str, StandardSet] = {}

    def load_by_loader(self, loader: StandardSetLoader, name: Optional[str] = None) -> StandardSet:
        """
        从加载器加载标准集，并自动索引其中的文档
        """
        standard_set = loader.load()
        if name:
            standard_set.name = name
            standard_set.metadata.name = name
        
        # 缓存加载的标准集
        self._loaded_sets[standard_set.name] = standard_set
        
        return standard_set

    def load_from_directory(self, path: Path|str, dataset_name: str, name: Optional[str] = None) -> StandardSet:
        """
        从目录加载标准集
        
        Args:
            path: 标准集目录路径
            dataset_name: 标准集名称
            name: 标准集名称，如果为None则使用目录名
            
        Returns:
            加载的标准集
        """
        loader = DirectoryStandardSetLoader(path, dataset_name)
        return self.load_by_loader(loader, name)
        
    
    def create_standard_set(
        self, 
        name: str, 
        schema: Schema, 
        description: str = "",
        schema_type: str = "object"
    ) -> StandardSet:
        """
        创建新的空标准集
        
        Args:
            name: 标准集名称
            schema: 数据模式
            description: 描述信息
            schema_type: 数据类型
            
        Returns:
            新创建的标准集
        """
        if name in self._loaded_sets:
            raise ValueError(f"标准集 {name} 已存在")
        
        metadata = StandardSetMetadata(
            name=name,
            version="1.0.0",
            description=description,
            total_standards=0,
            train_count=0,
            test_count=0,
            schema_type=schema_type
        )
        
        standard_set = StandardSet(
            name=name,
            schema=schema,
            standards=[],
            metadata=metadata
        )
        
        self._loaded_sets[name] = standard_set
        return standard_set
    
    
    def remove_standard_set(self, name: str) -> bool:
        """
        从内存中移除标准集
        
        Args:
            name: 标准集名称
            
        Returns:
            是否成功移除
        """
        if name in self._loaded_sets:
            del self._loaded_sets[name]
            return True
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取管理器统计信息
        
        Returns:
            统计信息字典
        """
        total_standards = sum(len(std_set) for std_set in self._loaded_sets.values())
        
        return {
            "loaded_sets_count": len(self._loaded_sets),
            "total_standards": total_standards,
            "sets_info": {
                name: {
                    "standards_count": len(std_set),
                    "schema_fields": len(std_set.schema.fields),
                    "schema_type": std_set.metadata.schema_type
                }
                for name, std_set in self._loaded_sets.items()
            },
        }
    
