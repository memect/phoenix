import pytest
from unittest.mock import Mock, AsyncMock, patch

from simple_workflow.services.llm_interaction import LLMInteractionService


@pytest.fixture
def mock_evaluation_engine():
    """模拟评估引擎"""
    engine = Mock()
    engine.evaluate_program = AsyncMock()
    return engine


@pytest.fixture
def llm_service(mock_llms, mock_evaluation_engine):
    """创建LLMInteractionService实例"""
    return LLMInteractionService(
        llms=mock_llms,
        evaluation_engine=mock_evaluation_engine,
        keys=["key1", "key2"]
    )


@pytest.mark.asyncio
async def test_reflect(llm_service, mock_llms):
    """测试反思功能"""
    mock_response = Mock()
    mock_response.content = "优化建议：修改提取逻辑"
    mock_llms.code_llm.ainvoke.return_value = mock_response
    
    suggestion, input_msgs, output = await llm_service.reflect(
        current_program_info="当前代码版本: v1",
        report="评估报告",
        recent_history="历史记录",
    )
    
    assert suggestion == "优化建议：修改提取逻辑"
    assert isinstance(input_msgs, list)
    assert len(input_msgs) == 2
    assert output == "优化建议：修改提取逻辑"
    mock_llms.code_llm.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_optimize_success(llm_service, mock_llms, mock_evaluation_engine, sample_program):
    """测试优化成功"""
    mock_response = Mock()
    mock_response.content = "<code>def extract(doc): return {'optimized': True}</code>"
    mock_llms.code_llm.ainvoke.return_value = mock_response
    
    mock_evaluation_engine.evaluate_program.return_value = sample_program.evaluation_result
    
    with patch('simple_workflow.services.generators.llm.extract_code_from_response') as mock_extract:
        mock_extract.return_value = "def extract(doc): return {'optimized': True}"
        
        new_program, input_msgs, output = await llm_service.optimize(
            current_program=sample_program,
            current_program_info="当前代码版本: v1",
            report="报告",
            suggestion="建议",
            recent_history="历史",
        )
        
        assert new_program is not None
        assert isinstance(input_msgs, list)
        assert len(input_msgs) == 2
        mock_extract.assert_called_once()
        mock_evaluation_engine.evaluate_program.assert_called_once()


@pytest.mark.asyncio
async def test_optimize_no_code_extracted(llm_service, mock_llms, mock_evaluation_engine, sample_program):
    """测试无法提取代码时使用原代码"""
    mock_response = Mock()
    mock_response.content = "这是没有代码块的响应"
    mock_llms.code_llm.ainvoke.return_value = mock_response
    
    mock_evaluation_engine.evaluate_program.return_value = sample_program.evaluation_result
    
    with patch('simple_workflow.services.generators.llm.extract_code_from_response') as mock_extract:
        mock_extract.return_value = None
        
        new_program, input_msgs, output = await llm_service.optimize(
            current_program=sample_program,
            current_program_info="当前代码版本: v1",
            report="报告",
            suggestion="建议",
            recent_history="历史",
        )
        
        assert new_program is not None
        mock_evaluation_engine.evaluate_program.assert_called_once()


def test_get_current_program_info(llm_service, sample_program):
    """测试获取当前程序信息"""
    info = llm_service.get_current_program_info(sample_program)
    
    assert sample_program.version in info
    assert sample_program.program in info
    assert "<code>" in info
    assert "</code>" in info
