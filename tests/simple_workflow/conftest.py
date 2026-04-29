import uuid
from datetime import datetime
from unittest.mock import Mock, AsyncMock
import pytest

from simple_workflow.models import Program
from evaluator.core.models import EvaluationResult, RecordDetailBase
from evaluator.core.evaluation_models import EvaluationStandard, EvaluationExtraction, RuntimeInfo, Document, Info
from simple_workflow.models import LLMS
from simple_workflow.settings import SimpleWorkflowSettings
from simple_workflow.recorder import WorkflowRecorder
from simple_workflow.related_info import StdInfo
from langchain_llm.models import LLM, OpenAILLMConfig


# 测试用的 LLM 配置
TEST_LLM_CONFIG = {
    "test_code_llm": LLM(
        type="openai",
        config=OpenAILLMConfig(
            model="test-model",
            api_key="test-key",
            api_base="http://localhost:8000",
        ),
    ),
    "test_summary_llm": LLM(
        type="openai",
        config=OpenAILLMConfig(
            model="test-model",
            api_key="test-key",
            api_base="http://localhost:8000",
        ),
    ),
}


@pytest.fixture
def mock_settings():
    """模拟配置，禁用记录功能"""
    return SimpleWorkflowSettings(
        enable_recording=False,
        recording_fail_silently=True,
        llm_config=TEST_LLM_CONFIG,
        code_llm="test_code_llm",
        summary_llm="test_summary_llm",
    )


@pytest.fixture
def mock_settings_with_recording():
    """模拟配置，启用记录功能（使用内存数据库）"""
    return SimpleWorkflowSettings(
        enable_recording=True,
        database_url="sqlite:///:memory:",
        recording_fail_silently=False,
        llm_config=TEST_LLM_CONFIG,
        code_llm="test_code_llm",
        summary_llm="test_summary_llm",
    )


@pytest.fixture
def mock_llms():
    """模拟LLM客户端"""
    code_llm = Mock()
    code_llm.ainvoke = AsyncMock()
    
    summary_llm = Mock()
    summary_llm.ainvoke = AsyncMock()
    
    return LLMS(code_llm=code_llm, summary_llm=summary_llm)


@pytest.fixture
def mock_recorder(mock_settings):
    """模拟记录器（禁用记录）"""
    return WorkflowRecorder(
        workflow_id=uuid.uuid4(),
        settings=mock_settings,
    )


@pytest.fixture
def mock_recorder_enabled(mock_settings_with_recording):
    """模拟记录器（启用记录）"""
    return WorkflowRecorder(
        workflow_id=uuid.uuid4(),
        settings=mock_settings_with_recording,
    )


@pytest.fixture
def sample_program():
    """示例程序对象"""
    evaluation_result = Mock(spec=EvaluationResult)
    evaluation_result.overall_accuracy = 0.75
    evaluation_result.field_stats = {}
    evaluation_result.details = []
    evaluation_result.llm_overall_report = Mock(return_value="测试报告")
    evaluation_result.get_error_details = Mock(return_value=[])
    evaluation_result.get_incorrect_details = Mock(return_value=[])
    
    return Program(
        version=uuid.uuid4().hex,
        program="def extract(doc): return {}",
        evaluation_result=evaluation_result,
    )


@pytest.fixture
def sample_detail():
    """示例RecordDetailBase对象"""
    detail = Mock(spec=RecordDetailBase)
    
    # 设置标准信息
    standard_info = Mock(spec=EvaluationStandard)
    standard_info.id = "test_std_001"
    standard_info.labels = {"field1": "value1"}
    standard_info.info = Mock(spec=Info)
    standard_info.info.document = Mock(spec=Document)
    standard_info.info.document.md = "# 测试文档\n测试内容"
    
    # 设置提取信息
    extracted_info = Mock(spec=EvaluationExtraction)
    extracted_info.runtime_info = Mock(spec=RuntimeInfo)
    extracted_info.runtime_info.stdout = "stdout output"
    extracted_info.runtime_info.stderr = "stderr output"
    
    detail.standared_info = standard_info
    detail.extracted_info = extracted_info
    detail.standard_value = {"field1": "value1"}
    detail.extracted_value = {"field1": "value2"}
    
    return detail


@pytest.fixture
def sample_std_info_map():
    """示例std_info_map"""
    return {
        "test_std_001": StdInfo(
            id="test_std_001",
            std_value={"field1": "value1"},
            md="# 测试文档\n测试内容",
        ),
        "test_std_002": StdInfo(
            id="test_std_002",
            std_value={"field2": "value2"},
            md="# 测试文档2\n测试内容2",
        ),
    }
