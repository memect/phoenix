import pytest
from unittest.mock import Mock, AsyncMock, patch

from simple_workflow.services.reporting import ReportBuilder
from evaluator.core.models import RecordDetailBase


@pytest.fixture
def report_builder(mock_llms):
    """创建ReportBuilder实例"""
    return ReportBuilder(
        summary_llm=mock_llms.summary_llm,
        run_type="test_run_type"
    )


def test_build_code_diff_no_change(report_builder):
    """测试代码无变化时的diff"""
    code = "def extract(doc): return {}"
    diff = report_builder.build_code_diff(code, code)
    assert diff == "代码未变更"


def test_build_code_diff_with_changes(report_builder):
    """测试有变化时的diff"""
    prev_code = "def extract(doc):\n    return {}"
    curr_code = "def extract(doc):\n    return {'new': 'field'}"
    
    diff = report_builder.build_code_diff(curr_code, prev_code)
    assert "修改前" in diff
    assert "修改后" in diff
    assert diff != "代码未变更"


def test_build_code_diff_empty_prev(report_builder):
    """测试从空代码的diff"""
    curr_code = "def extract(doc): return {}"
    diff = report_builder.build_code_diff(curr_code, "")
    assert diff != "代码未变更"


@pytest.mark.asyncio
async def test_build_summary(report_builder, sample_program):
    """测试构建summary"""
    summary = await report_builder.build_summary(
        last_round_summary="测试优化",
        prev_program=None,
        current_program=sample_program,
    )
    
    assert "summary: 测试优化" in summary
    assert "代码版本" in summary
    assert "code_diff:" in summary


@pytest.mark.asyncio
async def test_build_summary_with_prev_program(report_builder, sample_program):
    """测试有前一个程序时的summary"""
    prev_program = Mock()
    prev_program.version = "prev_version"
    prev_program.program = "def extract(doc): return {}"
    prev_program.evaluation_result = Mock()
    prev_program.evaluation_result.overall_accuracy = 0.6
    
    sample_program.evaluation_result.get_t2f_details = Mock(return_value=[])
    sample_program.evaluation_result.get_f2t_details = Mock(return_value=[])
    
    summary = await report_builder.build_summary(
        last_round_summary="测试优化",
        prev_program=prev_program,
        current_program=sample_program,
    )
    
    assert "对比版本" in summary
    assert "从错误变为正确的案例数" in summary


@pytest.mark.asyncio
async def test_build_source_report(report_builder, sample_detail, sample_std_info_map):
    """测试构建源信息报告"""
    with patch('simple_workflow.services.reporting.RelatedInfoExtract') as MockExtract:
        mock_extract = MockExtract.return_value
        mock_extract.get_info_by_std_info_from_files = AsyncMock(return_value=[])
        
        report = await report_builder.build_source_report(
            details=[sample_detail],
            std_info_map=sample_std_info_map,
            detail_report_count=1
        )
        
        assert isinstance(report, str)
        assert len(report) > 0


@pytest.mark.asyncio
async def test_build_source_report_with_detail_count(report_builder, sample_detail, sample_std_info_map):
    """测试detail_report_count参数"""
    detail1 = sample_detail
    detail2 = Mock(spec=RecordDetailBase)
    detail2.standared_info = Mock()
    detail2.standared_info.id = "test_std_002"
    detail2.extracted_info = Mock()
    detail2.extracted_info.runtime_info = Mock()
    detail2.extracted_info.runtime_info.stdout = "stdout2"
    detail2.extracted_info.runtime_info.stderr = "stderr2"
    detail2.standard_value = {"field": "std"}
    detail2.extracted_value = {"field": "ext"}
    
    with patch('simple_workflow.services.reporting.RelatedInfoExtract') as MockExtract:
        mock_extract = MockExtract.return_value
        mock_extract.get_info_by_std_info_from_files = AsyncMock(return_value=[])
        
        report = await report_builder.build_source_report(
            details=[detail1, detail2],
            std_info_map=sample_std_info_map,
            detail_report_count=2
        )
        
        assert isinstance(report, str)
        mock_extract.get_info_by_std_info_from_files.assert_called_once_with([])


def test_build_detail_report(report_builder, sample_detail):
    """测试构建详细报告"""
    report = report_builder._build_detail_report([sample_detail])
    
    assert "test_std_001" in report
    assert "stdout output" in report
    assert "stderr output" in report
