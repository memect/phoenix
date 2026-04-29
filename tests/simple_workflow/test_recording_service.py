import uuid
import pytest
from unittest.mock import Mock, call

from simple_workflow.services.recording import RecordingService
from simple_workflow.identity import ProgramIdentity


def test_start_workflow_when_recording_enabled(mock_recorder_enabled):
    """测试启用记录时启动工作流"""
    service = RecordingService(mock_recorder_enabled)
    service.recorder.start_workflow = Mock()
    
    service.start_workflow(
        run_type="test_type",
        keys=["key1", "key2"],
        target_accuracy=0.9,
        max_iterations=10
    )
    
    service.recorder.start_workflow.assert_called_once_with(
        run_type="test_type",
        keys=["key1", "key2"],
        target_accuracy=0.9,
        max_iterations=10
    )


def test_start_workflow_when_recording_disabled(mock_recorder):
    """测试禁用记录时不调用recorder"""
    service = RecordingService(mock_recorder)
    service.recorder.start_workflow = Mock()
    
    service.start_workflow(
        run_type="test_type",
        keys=["key1", "key2"],
        target_accuracy=0.9,
        max_iterations=10
    )
    
    service.recorder.start_workflow.assert_not_called()


def test_save_program_when_enabled(mock_recorder_enabled, sample_program):
    """测试启用记录时保存程序和评估"""
    service = RecordingService(mock_recorder_enabled)
    service.recorder.record_program = Mock()
    service.recorder.record_evaluation_result = Mock()
    
    # 创建 ProgramIdentity，使用 sample_program 中的 mock evaluation_result
    identity = ProgramIdentity(sample_program)
    
    # 替换 evaluation_result 为一个可以被序列化的 mock
    mock_eval_result = Mock()
    mock_eval_result.model_dump.return_value = {
        'schema_': {'type': 'object'},
        'details': [],
    }
    mock_eval_result.total_records = 10
    mock_eval_result.total_correct = 8
    mock_eval_result.overall_accuracy = 0.8
    mock_eval_result.field_stats = {}
    identity.evaluation_result = mock_eval_result
    
    service.save_program(identity)
    
    service.recorder.record_program.assert_called_once()
    service.recorder.record_evaluation_result.assert_called_once()


def test_save_program_when_disabled(mock_recorder, sample_program):
    """测试禁用记录时不调用recorder"""
    service = RecordingService(mock_recorder)
    service.recorder.record_program = Mock()
    service.recorder.record_evaluation_result = Mock()
    
    # 创建 ProgramIdentity
    identity = ProgramIdentity(sample_program)
    
    service.save_program(identity)
    
    service.recorder.record_program.assert_not_called()
    service.recorder.record_evaluation_result.assert_not_called()


def test_save_steps_when_enabled(mock_recorder_enabled, sample_program):
    """测试启用记录时记录各个步骤"""
    service = RecordingService(mock_recorder_enabled)
    service.recorder.record_step = Mock()
    
    # 创建 ProgramIdentity
    identity = ProgramIdentity(sample_program)
    
    service.save_init_step()
    service.save_reflect_step(1, identity, [], "output", "result")
    service.save_optimize_step(1, identity, [], "output", "result")
    service.save_terminate_step(2, identity, "完成")
    
    assert service.recorder.record_step.call_count == 4


def test_save_steps_when_disabled(mock_recorder, sample_program):
    """测试禁用记录时不记录步骤"""
    service = RecordingService(mock_recorder)
    service.recorder.record_step = Mock()
    
    # 创建 ProgramIdentity
    identity = ProgramIdentity(sample_program)
    
    service.save_init_step()
    service.save_reflect_step(1, identity, [], "output", "result")
    
    service.recorder.record_step.assert_not_called()


def test_finish_workflow_when_enabled(mock_recorder_enabled):
    """测试启用记录时完成工作流"""
    service = RecordingService(mock_recorder_enabled)
    service.recorder.finish_workflow = Mock()
    
    service.finish_workflow(stop_reason='准确率达标')
    
    service.recorder.finish_workflow.assert_called_once_with('准确率达标')
