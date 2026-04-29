"""
Evaluation Engine

评估引擎类，使用新的 StandardSet 架构实现程序评估功能。

主要组件：
- StandardSetManager: 数据集管理
- DatasetBoundEvaluator: 简化的评估接口
- code_executor.execute: 程序执行
"""

import asyncio
import time
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Literal, Tuple, Any, TYPE_CHECKING, Callable, TypedDict

from evaluator.standards.manager import StandardSetManager
from evaluator.standards.models import StandardSet, StandardSetMetadata, FullSchema
from evaluator.core.evaluation_models import FullStandard, FullExtractedResult
from evaluator.core.models import EvaluationResult, RecordDetailBase

# 使用 code_executor 模块
from code_executor.executor import execute

if TYPE_CHECKING:
    from simple_workflow.models import ResultJson


# 进度回调类型定义
class ProgressStart(TypedDict):
    """任务开始事件"""
    event: Literal['start']
    std_id: str
    total: int


class ProgressDone(TypedDict):
    """任务完成事件"""
    event: Literal['done']
    std_id: str
    completed: int
    total: int
    success: bool
    elapsed: float


ProgressEvent = ProgressStart | ProgressDone
ProgressCallback = Callable[[ProgressEvent], Any]


class EvaluationEngine:
    """
    评估引擎类，使用新的StandardSet架构实现程序评估功能。
    
    主要组件：
    - StandardSetManager: 数据集管理
    - DatasetBoundEvaluator: 简化的评估接口
    - code_executor.to_plain_article: 文档转换
    - code_executor.execute: 程序执行
    """
    
    def __init__(
        self, 
        train_dataset: StandardSet, 
        test_dataset: StandardSet, 
        keys: Optional[List[str]] = None,
        prog_run_concurrent: int = 1
    ):
        """
        初始化评估引擎。
        
        Args:
            train_dataset: 训练数据集
            test_dataset: 测试数据集
            keys: 可选的字段列表，仅评估指定字段
            prog_run_concurrent: 运行程序使用的并发数
        """
        self.train_dataset = train_dataset
        self.test_dataset = test_dataset
        
        # 获取绑定的评估器
        self.train_evaluator = self.train_dataset.get_evaluator()
        self.test_evaluator = self.test_dataset.get_evaluator()
        
        # 保存基础信息
        self.schema = self.train_dataset.schema
        self.schema_type = self.train_dataset.metadata.schema_type

        self.keys = keys
        
        # 运行程序使用的并发数
        self.prog_run_concurrent = prog_run_concurrent
    
    def _filter_dataset_by_keys(self, dataset: StandardSet, keys: List[str]) -> StandardSet:
        """创建一个预过滤的数据集副本，只包含指定字段"""
        
        # 验证字段存在性
        invalid_keys = [k for k in keys if k not in dataset.schema.fields]
        if invalid_keys:
            raise ValueError(f"字段 {invalid_keys} 在 schema 中不存在")
        
        # 过滤schema
        filtered_schema = FullSchema(type=dataset.schema.type, fields={
            k: v for k, v in dataset.schema.fields.items() if k in keys
        })
        
        # 过滤所有标准答案的labels
        filtered_standards = []
        for std in dataset.standards:
            filtered_labels = {k: v for k, v in std.labels.items() if k in keys}
            filtered_std = FullStandard(
                id=std.id,
                labels=filtered_labels,
                info=std.info,
                metadata=std.metadata,
                created_at=std.created_at,
                updated_at=std.updated_at
            )
            filtered_standards.append(filtered_std)
        
        # 创建过滤后的数据集
        filtered_metadata = StandardSetMetadata(
            name=f"{dataset.metadata.name}_filtered_{len(keys)}fields",
            description=f"过滤版本，包含字段: {', '.join(keys)}",
            schema_type=dataset.metadata.schema_type,
            version=dataset.metadata.version,
            created_at=dataset.metadata.created_at,
            total_standards=len(filtered_standards),
            train_count=len(filtered_standards),  # 简化处理，假设都是训练数据
            test_count=0
        )
        
        return StandardSet(
            name=filtered_metadata.name,
            schema=filtered_schema,
            standards=filtered_standards,
            metadata=filtered_metadata
        )
        
    def _get_dataset_for_keys(self, eval_type: str, keys: Optional[List[str]]):
        """根据字段需求获取对应的评估器"""
        base_dataset = self.train_dataset if eval_type == 'train' else self.test_dataset
        
        if keys:
            # 创建过滤后的数据集和评估器
            filtered_dataset = self._filter_dataset_by_keys(base_dataset, keys)
            return filtered_dataset
        return base_dataset

        
    async def evaluate_program_on_std_id(
        self, 
        program: str, 
        std_id: str, 
        keys: Optional[List[str]] = None
    ) -> RecordDetailBase | None:
        """评估程序在单个文档上的表现
        
        Args:
            program: 要评估的程序代码字符串
            std_id: 文档 ID
            keys: 可选的字段列表，仅评估指定字段
            
        Returns:
            RecordDetailBase | None: 评估详情，如果文档不存在返回 None
        """
        dataset = self._get_dataset_for_keys('train', keys or self.keys)
        evaluator = dataset.get_evaluator()
        standard = dataset.get_standard(std_id)
        if standard is None:
            return None
        extracted_result, _ = await self._extract_from_document(standard, program=program)
        return evaluator.evaluate_by_std_id(extracted_result, std_id)
    
    async def evaluate_program_on_std_ids(
        self,
        program: str,
        std_ids: List[str],
        keys: Optional[List[str]] = None
    ) -> Dict[str, RecordDetailBase | None]:
        """评估程序在多个指定文档上的表现
        
        Args:
            program: 要评估的程序代码字符串
            std_ids: 文档 ID 列表
            keys: 可选的字段列表，仅评估指定字段
            
        Returns:
            {std_id: RecordDetailBase | None} 字典
            - 如果文档不存在，对应值为 None
        """
        dataset = self._get_dataset_for_keys('train', keys or self.keys)
        evaluator = dataset.get_evaluator()
        
        # 收集存在的标准数据
        standards_map: Dict[str, FullStandard] = {}
        results: Dict[str, RecordDetailBase | None] = {}
        
        for std_id in std_ids:
            standard = dataset.get_standard(std_id)
            if standard is None:
                results[std_id] = None
            else:
                standards_map[std_id] = standard
        
        if not standards_map:
            return results
        
        # 并发执行提取任务
        semaphore = asyncio.Semaphore(self.prog_run_concurrent)
        
        async def extract_with_semaphore(std_id: str, standard: FullStandard):
            async with semaphore:
                extracted_result, _ = await self._extract_from_document(standard, program=program)
                return std_id, extracted_result
        
        tasks = [
            extract_with_semaphore(std_id, standard)
            for std_id, standard in standards_map.items()
        ]
        
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        for result in task_results:
            if isinstance(result, Exception):
                continue
            std_id, extracted_result = result
            detail = evaluator.evaluate_by_std_id(extracted_result, std_id)
            results[std_id] = detail
        
        return results
    
    async def evaluate_program(
        self,
        program: 'str | dict | ResultJson | None' = None,
        eval_type: Literal['train', 'test'] = 'train',
        *,
        workspace: 'str | Path | None' = None,
        keys: Optional[List[str]] = None,
        std_ids: Optional[List[str]] = None,
        progress_callback: Optional[ProgressCallback] = None
    ) -> EvaluationResult:
        """
        评估程序在指定数据集上的表现。
        
        Args:
            program: 要评估的程序，支持三种格式：
                - str: 单个程序代码字符串
                - dict: ResultJson 格式 {'__type__': 'single'/'all', '__data__': ...}
                - ResultJson: 直接传入 ResultJson 对象
            eval_type: 评估类型，'train' 或 'test'
            workspace: workspace 目录路径，与 program 互斥
            keys: 可选的字段列表，仅评估指定字段（None 表示评估所有字段）
            std_ids: 可选的文档ID列表，仅评估指定文档（None 表示评估所有文档）
            progress_callback: 可选的进度回调函数，接收 ProgressEvent
            
        Returns:
            EvaluationResult: 包含详细准确率和分析报告的评估结果
            
        Raises:
            ValueError: 当 program 和 workspace 都未提供或同时提供时
            FileNotFoundError: 当必需文件不存在时
        """
        # 互斥检查
        if program is None and workspace is None:
            raise ValueError("必须提供 program 或 workspace")
        if program is not None and workspace is not None:
            raise ValueError("program 和 workspace 互斥，不能同时提供")
        # 获取对应的评估器和数据集（可能是过滤后的）
        dataset = self._get_dataset_for_keys(eval_type, keys or self.keys)
        evaluator = dataset.get_evaluator()
        
        # 筛选文档（如果指定了 std_ids）
        if std_ids is not None:
            # 只评估指定的文档
            standards_to_evaluate = [
                std for std in dataset.standards if std.id in std_ids
            ]
            # 验证文档是否存在
            found_ids = {std.id for std in standards_to_evaluate}
            missing_ids = set(std_ids) - found_ids
            if missing_ids:
                raise ValueError(f"文档 {missing_ids} 不存在于{eval_type}数据集中")
        else:
            standards_to_evaluate = dataset.standards
        
        # 执行程序并收集结果（使用并发）
        extracted_results = []
        extra_infos = []
        
        # 使用信号量控制并发数量，避免过多的并发请求
        semaphore = asyncio.Semaphore(self.prog_run_concurrent)
        total = len(standards_to_evaluate)
        completed_count = 0
        completed_lock = asyncio.Lock()
        
        async def extract_with_semaphore(standard: FullStandard):
            nonlocal completed_count
            
            # 报告开始
            if progress_callback:
                progress_callback({
                    'event': 'start',
                    'std_id': standard.id,
                    'total': total
                })
            
            start_time = time.time()
            async with semaphore:
                result = await self._extract_from_document(
                    standard, program=program, workspace=workspace
                )
            elapsed = time.time() - start_time
            
            # 判断成功/失败
            extracted_result, _ = result
            success = extracted_result.success
            
            # 报告完成
            async with completed_lock:
                completed_count += 1
                if progress_callback:
                    progress_callback({
                        'event': 'done',
                        'std_id': standard.id,
                        'completed': completed_count,
                        'total': total,
                        'success': success,
                        'elapsed': elapsed
                    })
            
            return result
        
        # 并发执行所有提取任务
        results = await asyncio.gather(
            *[extract_with_semaphore(std) for std in standards_to_evaluate],
            return_exceptions=True
        )
        
        # 处理结果，分离 extracted_result 和 extra_info
        for result in results:
            if isinstance(result, Exception):
                # 如果某个任务失败，创建错误结果
                error_result = FullExtractedResult.error_result(
                    exception=result, 
                    stdout="", 
                    stderr=str(result)
                )
                extracted_results.append(error_result)
                extra_infos.append({})
            else:
                # 正常结果是一个包含两个元素的元组
                extracted_result, extra_info = result
                extracted_results.append(extracted_result)
                extra_infos.append(extra_info)
        
        # 使用简化的评估接口
        return evaluator.evaluate(extracted_results, extra_infos=extra_infos)

    
    async def _extract_from_document(
        self,
        standard: FullStandard,
        *,
        program: 'str | dict | ResultJson | None' = None,
        workspace: 'str | Path | None' = None,
    ) -> Tuple[FullExtractedResult, Dict[str, Any]]:
        """从文档提取数据
        
        Args:
            standard: 标准数据
            program: 程序代码/配置
            workspace: workspace 目录路径
        """
        # 延迟导入避免循环依赖
        try:
            from simple_workflow.models import ResultJson
            has_result_json = True
        except ImportError:
            has_result_json = False
            ResultJson = None
        
        if standard.info is None or standard.info.document is None:
            raise ValueError(f"标准数据 {standard.id} 缺少文档信息")
        
        document = standard.info.document
        docjson = document.docjson
        pdf_bytes = document.get_pdf_bytes()
        
        # 执行提取
        try:
            if workspace is not None:
                # workspace 模式
                extracted_data = await execute(
                    workspace=workspace, docjson=docjson, pdf_bytes=pdf_bytes
                )
                stdout, stderr = "", ""
            elif isinstance(program, str):
                # 程序代码字符串
                extracted_data, stdout, stderr = await execute(
                    program=program, docjson=docjson, pdf_bytes=pdf_bytes, capture_output=True
                )
            elif has_result_json and isinstance(program, ResultJson):
                raise ValueError(
                    "ResultJson/config flat 旧格式已不再支持。请改用 workspace/program "
                    "并使用 Document 输入。"
                )
            else:
                raise ValueError(
                    "config flat 旧格式已不再支持。请改用 workspace/program "
                    "并使用 Document 输入。"
                )
            
            extracted_data = FullExtractedResult.success_result(
                extracted_data,
                stdout=stdout,
                stderr=stderr
            )
            
        except Exception as e:
            extracted_data = FullExtractedResult.error_result(
                exception=e, 
                stdout="", 
                stderr=traceback.format_exc()
            )
        
        extra_info = {}
        return extracted_data, extra_info
    
    @classmethod
    def from_data_path(
        cls, 
        data_path: str, 
        keys: Optional[List[str]] = None,
        prog_run_concurrent: Optional[int] = None
    ):
        """从本地数据路径创建评估引擎
        
        Args:
            data_path: 数据目录路径，包含 schema.json、train.json/test.json 和 docjson 文件夹
            keys: 可选的字段列表，仅评估指定字段
            prog_run_concurrent: 程序执行并发数，None 表示从配置读取
            
        Returns:
            EvaluationEngine 实例
        """
        # 如果未指定并发数，从配置读取
        if prog_run_concurrent is None:
            from xdev.config import load_config
            prog_run_concurrent = load_config().eval_concurrent
        
        manager = StandardSetManager()
        
        # 加载训练和测试数据集
        train_dataset = manager.load_from_directory(data_path, "train")
        if not train_dataset.standards:
            raise ValueError(f"训练数据集 {data_path}/train 中没有标准数据")
        test_dataset = manager.load_from_directory(data_path, "test")
        return cls(
            train_dataset=train_dataset, 
            test_dataset=test_dataset, 
            keys=keys,
            prog_run_concurrent=prog_run_concurrent
        )
