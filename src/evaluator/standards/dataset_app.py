"""资源生成器 - 用于从API获取数据并生成标准数据集

此模块提供了一套可复用的函数，用于：
1. 从远程API获取数据
2. 下载和保存markdown、docjson等资源文件
3. 分割训练集和测试集
4. 生成用于评估的标准数据集
5. 通过DatasetApp管理标准集
"""

from math import ceil
import os
import httpx
import json
import uuid
from typing import Callable, Optional, Any, List
from pathlib import Path


class DatasetApp:
    """标准集管理类，用于从API获取和管理标准集数据
    
    支持新版API结构，返回格式：
    {
        "code": "200",
        "message": "成功",
        "data": {
            "name": "标准集名称",
            "id": "标准集ID", 
            "status": "ready",
            "document_ids": [...],
            "schema_def": {...}
        }
    }
    """
    
    def __init__(self, base_url: str = "http://localhost:8008", timeout: int = 60):
        """
        初始化标准集管理器
        
        Args:
            base_url: API基础地址
            timeout: HTTP请求超时时间（秒）
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
    
    def fetch_standard_set(self, set_id: str) -> dict:
        """
        从API获取标准集信息
        
        Args:
            set_id: 标准集ID
            
        Returns:
            API返回的标准集数据
            
        Example:
            >>> app = DatasetApp()
            >>> data = app.fetch_standard_set("b845724f-c1c0-4dce-ab91-c25bef3ae994")
            >>> print(data['data']['name'])
            O_临时公告_股东大会召开通知
        """
        url = f"{self.base_url}/api/standard-sets/{set_id}"
        print(f'正在获取标准集: {url}')
        response = self.client.get(url, headers={'accept': 'application/json'})
        response.raise_for_status()
        
        result = response.json()
        if result.get('code') != '200':
            raise ValueError(f"API返回错误: {result.get('message')}")
        
        return result
    
    def get_name(self, set_id: str) -> str:
        """
        获取标准集名称
        
        Args:
            set_id: 标准集ID
            
        Returns:
            标准集名称
        """
        data = self.fetch_standard_set(set_id)
        return data['data']['name']
    
    def get_document_ids(self, set_id: str) -> List[str]:
        """
        获取标准集中的所有文档ID
        
        Args:
            set_id: 标准集ID
            
        Returns:
            文档ID列表
        """
        data = self.fetch_standard_set(set_id)
        return data['data']['document_ids']
    
    def get_schema(self, set_id: str) -> Optional[dict]:
        """
        获取标准集的schema定义
        
        Args:
            set_id: 标准集ID
            
        Returns:
            schema定义字典，如果不存在则返回None
        """
        data = self.fetch_standard_set(set_id)
        return data['data'].get('schema_def')
    
    def get_info(self, set_id: str) -> dict:
        """
        获取标准集的完整信息
        
        Args:
            set_id: 标准集ID
            
        Returns:
            包含名称、ID、状态、文档数量等信息的字典
        """
        data = self.fetch_standard_set(set_id)
        dataset_info = data['data']
        
        return {
            'id': dataset_info['id'],
            'name': dataset_info['name'],
            'status': dataset_info['status'],
            'created_at': dataset_info['created_at'],
            'document_count': len(dataset_info['document_ids']),
            'document_ids': dataset_info['document_ids'],
            'has_schema': dataset_info.get('schema_def') is not None,
            'tags': dataset_info.get('tags')
        }
    
    def fetch_data(self, url: str) -> dict:
        """
        从任意URL获取数据（通用方法）
        
        Args:
            url: 完整的API地址
            
        Returns:
            API返回的JSON数据
        """
        print(f'正在获取数据: {url}')
        response = self.client.get(url, headers={'accept': 'application/json'})
        response.raise_for_status()
        return response.json()
    
    def fetch_documents_info(self, set_id: str, with_md: bool = False) -> dict:
        """
        获取标准集的文档信息（旧版API）
        
        Args:
            set_id: 标准集ID
            with_md: 是否包含markdown内容
            
        Returns:
            文档信息数据
        """
        url = f"{self.base_url}/dev-api/documents_info/{set_id}?with_md={str(with_md).lower()}"
        return self.fetch_data(url)

    def get_schema_from_data(self, set_id: str) -> dict:
        """
        从标准集的 standard_data 自动推断 schema。
        
        优先使用 schema_def（如果存在），否则从文档数据推断。
        
        Args:
            set_id: 标准集ID
            
        Returns:
            内部 schema 格式:
            {
                "type": "object" | "list_of_objects",
                "data": {"field_name": "str" | "int" | ...}
            }
            
        Raises:
            ValueError: 无法推断 schema
            
        Example:
            >>> app = DatasetApp()
            >>> schema = app.get_schema_from_data("c84ee54b-cc83-4d6d-b79f-f9268b3e32ed")
            >>> print(schema)
            {'type': 'object', 'data': {'原文_会议名称': 'str', ...}}
        """
        # 1. 先尝试获取 schema_def
        schema_def = self.get_schema(set_id)
        if schema_def is not None:
            return schema_def
        
        # 2. 从文档数据推断
        print(f"schema_def 为空，从文档数据推断 schema...")
        docs_info = self.fetch_documents_info(set_id, with_md=False)
        
        if not docs_info.get('data'):
            raise ValueError(f"标准集 {set_id} 没有文档数据")
        
        # 收集所有 standard_data
        standard_datas = []
        for item in docs_info['data']:
            std_data = item.get('standard_data')
            if std_data is not None:
                standard_datas.append({'labels': std_data})
        
        if not standard_datas:
            raise ValueError(f"标准集 {set_id} 的文档没有 standard_data")
        
        # 使用 ResourceGenerator 的 schema 推断逻辑
        generator = ResourceGenerator(name="temp", dataset_app=self)
        return generator.generate_schema(standard_datas)

    def get_json_schema(self, set_id: str) -> dict:
        """
        获取标准 JSON Schema 格式的 schema。
        
        先获取内部 schema，然后转换为标准 JSON Schema 格式。
        
        Args:
            set_id: 标准集ID
            
        Returns:
            标准 JSON Schema 格式:
            - object 类型: {"type": "object", "properties": {...}, "required": [...]}
            - list_of_objects 类型: {"type": "array", "items": {"type": "object", ...}}
            
        Raises:
            ValueError: 无法获取或转换 schema
            
        Example:
            >>> app = DatasetApp()
            >>> json_schema = app.get_json_schema("c84ee54b-cc83-4d6d-b79f-f9268b3e32ed")
            >>> print(json_schema)
            {'type': 'object', 'properties': {'原文_会议名称': {'type': 'string'}, ...}}
        """
        internal_schema = self.get_schema_from_data(set_id)
        return self._convert_to_json_schema(internal_schema)

    @staticmethod
    def _convert_to_json_schema(internal_schema: dict) -> dict:
        """
        将内部 schema 格式转换为标准 JSON Schema。
        
        Args:
            internal_schema: 内部 schema 格式
            
        Returns:
            标准 JSON Schema
        """
        type_mapping = {
            "str": {"type": "string"},
            "int": {"type": "integer"},
            "float": {"type": "number"},
            "bool": {"type": "boolean"},
            "list": {"type": "array", "items": {}},
            "object": {"type": "object"},
        }
        
        schema_type = internal_schema.get("type", "object")
        data = internal_schema.get("data", {})
        
        # 构建 properties
        properties = {}
        for field_name, field_type in data.items():
            properties[field_name] = type_mapping.get(field_type, {"type": "string"})
        
        # 构建 object schema
        object_schema = {
            "type": "object",
            "properties": properties,
            "required": list(data.keys()),
        }
        
        if schema_type == "list_of_objects":
            return {
                "type": "array",
                "items": object_schema,
            }
        else:
            return object_schema


class ResourceGenerator:
    """资源生成器类，封装数据集生成的完整流程"""
    
    def __init__(
        self, 
        name: str, 
        base_dir: str = "resources",
        timeout: int = 60,
        dataset_app: Optional[DatasetApp] = None
    ):
        """
        初始化资源生成器
        
        Args:
            name: 数据集名称，用于创建目录
            base_dir: 基础目录，默认为 "resources"
            timeout: HTTP请求超时时间（秒）
            dataset_app: 可选的 DatasetApp 实例，用于数据获取
        """
        self.name = name
        self.base_dir = Path(base_dir)
        self.timeout = timeout
        
        # 使用提供的 DatasetApp 或创建新实例
        self.dataset_app = dataset_app or DatasetApp(timeout=timeout)
        
        # 目录路径
        self.docjson_dir = self.base_dir / name / "docjson"
        self.pdf_dir = self.base_dir / name / "pdf"
        self.standard_for_evaluate_dir = self.base_dir / name / "standard_for_evaluate"
    
    def create_dirs(self) -> None:
        """创建必要的资源目录"""
        self.docjson_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.standard_for_evaluate_dir.mkdir(parents=True, exist_ok=True)
    
    def fetch_documents_info(self, set_id: str, with_md: bool = False) -> dict:
        """
        获取标准集的文档信息（委托给 DatasetApp）
        
        Args:
            set_id: 标准集ID
            with_md: 是否包含markdown内容
            
        Returns:
            文档信息数据
        """
        return self.dataset_app.fetch_documents_info(set_id, with_md)
    
    def process_standard_data(
        self, 
        raw_data: dict,
        processor: Optional[Callable[[dict], dict]] = None
    ) -> list[dict]:
        """
        处理标准数据
        
        Args:
            raw_data: 原始API数据
            processor: 可选的处理函数，用于转换standard_data字段
            
        Returns:
            处理后的标准数据列表
        """
        standard_datas = []
        
        for item in raw_data['data']:
            std_data = item['standard_data']
            
            # 如果提供了处理函数，则应用处理
            if processor:
                std_data = processor(std_data)
            
            standard_datas.append({
                'markdown': item['md_content'],
                'labels': std_data,
                'id': item['id'],
                'document_id': item['document_id'],
                'md_link': item['md_link'],
                'pdf_link': item['pdf_link'],
                'docjson_link': item['docjson_link'],
                'filename': item['name'],
            })
        
        return standard_datas
    
    def download_resources(self, standard_datas: list[dict], download_pdf: bool = False) -> None:
        """
        下载并保存资源文件
        
        Args:
            standard_datas: 标准数据列表
            download_pdf: 是否下载 PDF 文件（默认 False）
        """
        for item in standard_datas:
            doc_id = uuid.UUID(item['document_id']).hex
            
            # 下载并保存docjson
            print(f"下载 docjson: {item['filename']}")
            docjson_data = httpx.get(item['docjson_link'], timeout=self.timeout).json()
            docjson_path = self.docjson_dir / f"{doc_id}.json"
            with open(docjson_path, "w") as f:
                json.dump(docjson_data, f, ensure_ascii=False, indent=4)
            
            # 下载并保存 PDF（可选）
            if download_pdf and item.get('pdf_link'):
                print(f"下载 PDF: {item['filename']}")
                try:
                    pdf_response = httpx.get(item['pdf_link'], timeout=self.timeout)
                    pdf_response.raise_for_status()
                    pdf_path = self.pdf_dir / f"{doc_id}.pdf"
                    pdf_path.write_bytes(pdf_response.content)
                except Exception as e:
                    print(f"警告: 下载 PDF 失败 {item['filename']}: {e}")
    
    def split_train_test(
        self,
        standard_datas: list[dict],
        max_size: int = 200,
        train_ratio: float = 2/3
    ) -> tuple[list[dict], list[dict]]:
        """
        分割训练集和测试集
        
        Args:
            standard_datas: 标准数据列表
            max_size: 最大使用数量
            train_ratio: 训练集比例
            
        Returns:
            (训练集, 测试集) 元组
        """
        num = len(standard_datas)
        use_num = min(num, max_size)
        mid = ceil(use_num * train_ratio)
        
        train_data = standard_datas[0:mid]
        test_data = standard_datas[mid:use_num]
        
        return train_data, test_data
    
    def save_dataset(
        self,
        data: list[dict],
        filename: str
    ) -> None:
        """
        保存数据集到文件
        
        Args:
            data: 数据列表
            filename: 文件名（相对于standard_for_evaluate_dir）
        """
        save_path = self.standard_for_evaluate_dir / filename
        with open(save_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"已保存: {save_path}")
    
    def save_info(self, train_count: int, test_count: int) -> None:
        """
        保存数据集信息
        
        Args:
            train_count: 训练集数量
            test_count: 测试集数量
        """
        info_path = self.standard_for_evaluate_dir / "info.txt"
        with open(info_path, "w") as f:
            f.write(f"train: {train_count}\n")
            f.write(f"test: {test_count}\n")
        print(f"已保存信息: {info_path}")
    
    def _infer_field_type(self, values: list) -> str:
        """
        推断字段类型
        
        规则：
        - 全是null -> 'str'
        - 只要有一个str -> 'str'
        - 只有null和同一种非str类型 -> 该类型
        - 有多种非str非null类型 -> 报错
        - 空列表[] -> 'list'
        - 空字典{} -> 报错
        
        Args:
            values: 字段值列表
            
        Returns:
            字段类型字符串
            
        Raises:
            ValueError: 类型不一致或包含空字典
        """
        types_found = set()
        
        for v in values:
            if v is None:
                continue  # 跳过null
            elif isinstance(v, str):
                return "str"  # 只要有str就立即返回str
            elif isinstance(v, dict):
                if len(v) == 0:
                    raise ValueError("字段值包含空字典 {}")
                types_found.add("object")
            elif isinstance(v, list):
                types_found.add("list")  # 空列表也是list
            elif isinstance(v, bool):
                # bool要在int之前检查，因为bool是int的子类
                types_found.add("bool")
            elif isinstance(v, int):
                types_found.add("int")
            elif isinstance(v, float):
                types_found.add("float")
            else:
                # 未知类型
                raise ValueError(f"未知的字段值类型: {type(v).__name__}")
        
        if len(types_found) == 0:
            return "str"  # 全是null
        elif len(types_found) == 1:
            return list(types_found)[0]
        elif types_found == {"int", "float"}:
            # int 和 float 共存时，统一为 float
            return "float"
        else:
            raise ValueError(f"字段有多种非str类型: {types_found}")
    
    def generate_schema(self, standard_datas: list[dict]) -> dict:
        """
        从标准数据生成schema
        
        Args:
            standard_datas: 标准数据列表
            
        Returns:
            schema字典
            
        Raises:
            ValueError: 字段类型不一致或包含空字典
        """
        if not standard_datas:
            raise ValueError("标准数据列表为空，无法生成schema")
        
        # 判断schema类型：检查第一个文档的labels是dict还是list
        first_labels = standard_datas[0].get('labels')
        if first_labels is None:
            raise ValueError("第一个文档的labels字段为空")
        
        is_list_type = isinstance(first_labels, list)
        schema_type = "list_of_objects" if is_list_type else "object"
        
        # 收集所有字段和它们的值
        field_values = {}
        
        for item in standard_datas:
            labels = item.get('labels', {} if not is_list_type else [])
            
            if is_list_type:
                # list_of_objects类型：labels是列表，需要遍历列表中的每个对象
                if not isinstance(labels, list):
                    actual_type = type(labels).__name__
                    raise ValueError(
                        f"文档 {item.get('id', 'unknown')} 的labels类型不一致: "
                        f"期望类型为 list (list_of_objects)，实际类型为 {actual_type}，"
                        f"值为: {labels}"
                    )
                for obj in labels:
                    if not isinstance(obj, dict):
                        raise ValueError(
                            f"文档 {item.get('id', 'unknown')} 的labels列表中包含非字典元素: "
                            f"期望元素类型为 dict，实际类型为 {type(obj).__name__}，值为: {obj}"
                        )
                    for field_name, field_value in obj.items():
                        if field_name not in field_values:
                            field_values[field_name] = []
                        field_values[field_name].append(field_value)
            else:
                # object类型：labels是字典
                if not isinstance(labels, dict):
                    actual_type = type(labels).__name__
                    raise ValueError(
                        f"文档 {item.get('id', 'unknown')} 的labels类型不一致: "
                        f"期望类型为 dict (object)，实际类型为 {actual_type}，"
                        f"值为: {labels}"
                    )
                for field_name, field_value in labels.items():
                    if field_name not in field_values:
                        field_values[field_name] = []
                    field_values[field_name].append(field_value)
        
        # 推断每个字段的类型
        schema_data = {}
        for field_name, values in field_values.items():
            try:
                field_type = self._infer_field_type(values)
                schema_data[field_name] = field_type
            except ValueError as e:
                raise ValueError(f"字段 '{field_name}' 类型推断失败: {e}")
        
        return {
            "type": schema_type,
            "data": schema_data
        }
    
    def generate(
        self,
        set_id: str,
        processor: Optional[Callable[[dict], dict]] = None,
        download_files: bool = True,
        download_pdf: bool = False,
        max_size: int = 200,
        train_ratio: float = 2/3,
        std_ids: Optional[List[str]] = None,
    ) -> None:
        """
        完整的数据集生成流程
        
        Args:
            set_id: 标准集ID
            processor: 可选的数据处理函数
            download_files: 是否下载资源文件
            download_pdf: 是否下载 PDF 文件
            max_size: 最大使用数量
            train_ratio: 训练集比例
            std_ids: 可选的文档 ID 白名单，仅下载和使用这些文档
        """
        # 创建目录
        self.create_dirs()

        # 获取数据
        raw_data = self.fetch_documents_info(set_id)

        # 处理数据
        standard_datas = self.process_standard_data(raw_data, processor)
        print(f"共获取 {len(standard_datas)} 条数据")

        # 白名单过滤
        if std_ids is not None:
            allowed = {_normalize_doc_id(s) for s in std_ids}
            before_count = len(standard_datas)
            standard_datas = [
                item for item in standard_datas
                if _normalize_doc_id(item['document_id']) in allowed
            ]
            print(f"白名单过滤: {before_count} → {len(standard_datas)} 条数据")

        # 先分割，再下载（避免下载未使用的文件）
        train_data, test_data = self.split_train_test(
            standard_datas,
            max_size=max_size,
            train_ratio=train_ratio
        )
        used_data = train_data + test_data

        # 只下载实际使用的资源
        if download_files:
            self.download_resources(used_data, download_pdf=download_pdf)
        
        # 保存数据集
        self.save_dataset(train_data, "train.json")
        self.save_dataset(test_data, "test.json")
        self.save_info(len(train_data), len(test_data))
        
        # 生成并保存schema
        schema = self.generate_schema(standard_datas)
        schema_path = self.base_dir / self.name / "schema.json"
        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, ensure_ascii=False, indent=4)
        print(f"已保存schema: {schema_path}")
        
        print(f"\n✓ 数据集生成完成:")
        print(f"  训练集: {len(train_data)} 条")
        print(f"  测试集: {len(test_data)} 条")


def _normalize_doc_id(doc_id: str) -> str:
    """将文档 ID 归一化为小写无连字符的 hex 格式，以便比较。"""
    return doc_id.replace("-", "").lower()


# 便捷函数
def generate_dataset(
    base_url: str,
    set_id: str,
    name: Optional[str] = None,
    processor: Optional[Callable[[dict], dict]] = None,
    base_dir: str = "resources",
    download_files: bool = True,
    download_pdf: bool = False,
    max_size: int = 200,
    train_ratio: float = 2/3,
    timeout: int = 60,
    std_ids: Optional[List[str]] = None,
) -> str:
    """
    快速生成数据集的便捷函数
    
    Args:
        base_url: API基础地址，如 "http://localhost:8008"
        set_id: 标准集ID
        name: 数据集名称，如果不提供则自动从API获取
        processor: 可选的数据处理函数
        base_dir: 基础目录
        download_files: 是否下载资源文件
        download_pdf: 是否下载 PDF 文件
        max_size: 最大使用数量
        train_ratio: 训练集比例
        timeout: HTTP请求超时时间
        std_ids: 可选的文档 ID 白名单，仅下载和使用这些文档
        
    Returns:
        生成的数据集目录路径
        
    Example:
        >>> path = generate_dataset(
        ...     base_url="http://localhost:8008",
        ...     set_id="b845724f-c1c0-4dce-ab91-c25bef3ae994"
        ... )
        >>> print(path)
        resources/O_临时公告_股东大会召开通知
    """
    # 创建 DatasetApp 实例
    dataset_app = DatasetApp(base_url=base_url, timeout=timeout)
    
    # 如果没有提供名称，从API获取
    if name is None:
        name = dataset_app.get_name(set_id)
        print(f"从API获取到标准集名称: {name}")
    
    # 创建资源生成器并生成数据集
    generator = ResourceGenerator(name, base_dir, timeout, dataset_app=dataset_app)
    generator.generate(
        set_id=set_id,
        processor=processor,
        download_files=download_files,
        download_pdf=download_pdf,
        max_size=max_size,
        train_ratio=train_ratio,
        std_ids=std_ids,
    )
    
    # 返回生成的目录路径
    from pathlib import Path
    return str(Path(base_dir) / name)
