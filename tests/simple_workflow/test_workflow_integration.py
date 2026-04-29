"""Simple Workflow 集成测试 - 使用 Mock LLM"""

import uuid
import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from langchain_core.messages import AIMessage

from simple_workflow.api import run_simple_workflow
from simple_workflow.settings import SimpleWorkflowSettings


@pytest.fixture
def temp_test_dir():
    """创建临时测试目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_llm_clients():
    """Mock LLM 客户端，返回预定义的程序代码"""
    
    # 迭代次数计数器
    iteration_count = {'count': 0}
    
    async def mock_code_llm_ainvoke(*args, **kwargs):
        """Mock 代码生成 LLM"""
        iteration_count['count'] += 1
        
        # 第一次返回一个准确率较低的程序
        if iteration_count['count'] == 1:
            code = '''def extract(article):
    """第一版：准确率较低"""
    return {
        "name": "",
        "age": 0
    }'''
        # 第二次返回一个准确率更高的程序
        elif iteration_count['count'] == 2:
            code = '''def extract(article):
    """第二版：准确率提升"""
    return {
        "name": "Unknown",
        "age": 0,
        "city": ""
    }'''
        else:
            # 第三次返回一个准确率很高的程序（收敛）
            code = '''def extract(article):
    """第三版：准确率很高，应该收敛"""
    return {
        "name": "Unknown",
        "age": 0,
        "city": "Unknown",
        "country": "Unknown"
    }'''
        
        return AIMessage(content=f"```python\n{code}\n```")
    
    async def mock_summary_llm_ainvoke(*args, **kwargs):
        """Mock 总结 LLM"""
        return AIMessage(content="程序改进建议：增加更多字段的提取")
    
    code_llm = Mock()
    code_llm.ainvoke = AsyncMock(side_effect=mock_code_llm_ainvoke)
    
    summary_llm = Mock()
    summary_llm.ainvoke = AsyncMock(side_effect=mock_summary_llm_ainvoke)
    
    return code_llm, summary_llm


@pytest.fixture
def test_dataset():
    """使用真实的 MSSS 数据集进行测试"""
    # 使用现有的真实数据集
    return "resources/MSSS_"


@pytest.mark.asyncio
async def test_simple_workflow_with_mock_llm(mock_llm_clients, test_dataset, temp_test_dir):
    """测试完整的 simple workflow 流程（使用 mock LLM）"""
    
    code_llm, summary_llm = mock_llm_clients
    result_file = temp_test_dir / "result.json"
    db_file = temp_test_dir / "test.db"
    
    # Mock SimpleWorkflowSettings 使用 SQLite
    from simple_workflow.settings import SimpleWorkflowSettings
    from langchain_llm.models import LLM, OpenAILLMConfig
    
    # 测试用的 LLM 配置
    test_llm_config = {
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
    
    with patch('simple_workflow.api.SimpleWorkflowSettings') as mock_settings_class:
        # 创建使用 SQLite 的设置
        test_settings = SimpleWorkflowSettings(
            enable_recording=True,
            database_url=f"sqlite:///{db_file}",
            llm_config=test_llm_config,
            code_llm="test_code_llm",
            summary_llm="test_summary_llm",
        )
        mock_settings_class.return_value = test_settings
        
        # Mock get_llm_client_by_model 函数
        with patch('langchain_llm.get_llm_client_by_model') as mock_get_llm:
            # 返回我们的 mock LLM
            def get_mock_llm(model_config):
                if 'code' in str(model_config).lower():
                    return code_llm
                else:
                    return summary_llm
            
            mock_get_llm.side_effect = get_mock_llm
            
            # 运行 workflow
            result_json = await run_simple_workflow(
                init_program='''def extract(article):
    """初始程序：准确率很低"""
    return {"name": ""}
''',
                data_path=test_dataset,
                target_accuracy=0.95,
                result_path=str(result_file),
                export_trace=True,
            )
    
    # 验证结果
    assert result_json is not None
    assert 'data' in result_json.model_dump()
    assert 'meta' in result_json.model_dump()
    
    meta = result_json.meta
    
    # 验证 trace 数据存在
    assert 'trace' in meta, "结果中应包含 trace 数据"
    
    trace = meta['trace']
    
    # 调试：输出完整的 trace 结构
    import json
    print("\n" + "="*80)
    print("完整 TRACE 结构:")
    print("="*80)
    print(json.dumps(trace, indent=2, ensure_ascii=False))
    print("="*80 + "\n")
    
    # 基本验证 - trace 结构
    assert 'metadata' in trace
    assert 'programs' in trace, "应包含 programs 字典"
    assert 'iterations' in trace
    assert 'final_result' in trace
    
    # 验证 metadata
    metadata = trace['metadata']
    assert 'workflow_id' in metadata
    assert 'start_time' in metadata
    
    # 验证 programs 字典
    programs = trace['programs']
    assert isinstance(programs, dict), "programs 应该是字典"
    print(f"✅ programs 字典包含 {len(programs)} 个程序")
    
    # 验证 programs 结构
    if len(programs) > 0:
        first_program_id = list(programs.keys())[0]
        first_program = programs[first_program_id]
        assert 'code' in first_program, "program 应包含 code"
        assert 'evaluations' in first_program, "program 应包含 evaluations"
        
        # 验证评估结果包含详细信息
        if len(first_program['evaluations']) > 0:
            evaluation = first_program['evaluations'][0]
            assert 'details' in evaluation, "评估结果应包含 details"
            
            # 验证 details 结构（如果有）
            if len(evaluation['details']) > 0:
                detail = evaluation['details'][0]
                assert 'extracted_info' in detail
                assert 'standared_info' in detail
                
                # 验证 standared_info 只有 id
                if detail['standared_info']:
                    assert 'id' in detail['standared_info']
                    # 确保没有其他字段
                    assert len(detail['standared_info']) == 1, "standared_info 应该只有 id 字段"
                
                print(f"✅ 验证通过：evaluation details 包含 extracted_info 和简化的 standared_info (只有id)")
    
    # 验证 iterations
    iterations = trace['iterations']
    assert len(iterations) > 0, "应该至少有一次迭代"
    
    # 验证第一次迭代
    first_iteration = iterations[0]
    assert 'round' in first_iteration
    assert 'steps' in first_iteration
    
    # 验证 step 中只有 program_id 引用
    found_program_ref = False
    if len(first_iteration['steps']) > 0:
        for step in first_iteration['steps']:
            if 'program_id' in step:
                found_program_ref = True
                program_id = step['program_id']
                # 验证这个 program_id 存在于 programs 字典中
                assert program_id in programs, f"step 引用的 program_id {program_id} 应该在 programs 字典中"
                # 确保 step 中没有嵌入完整的 program 数据
                assert 'program' not in step, "step 中不应该嵌入完整的 program 数据"
                print(f"✅ 验证通过：step 只保留 program_id 引用，完整数据在 programs 字典中")
                break
    
    if found_program_ref:
        print(f"✅ 验证通过：step 正确使用 program_id 引用")
    
    # 验证 final_result
    final_result = trace['final_result']
    assert 'status' in final_result
    
    # 验证 final_result 也使用 program_id 引用
    if 'best_program_id' in final_result:
        best_program_id = final_result['best_program_id']
        assert best_program_id in programs, f"final_result 引用的 program_id {best_program_id} 应该在 programs 字典中"
        print(f"✅ 验证通过：final_result 使用 best_program_id 引用")
    
    # 验证结果文件已保存
    assert result_file.exists()
    
    print(f"\n✅ 测试通过！")
    print(f"  - 总迭代次数: {len(iterations)}")
    print(f"  - 最终状态: {final_result['status']}")
    print(f"  - Trace 已成功导出到 result JSON")
    print(f"  - 结果文件: {result_file}")


@pytest.mark.asyncio
async def test_workflow_database_recording(mock_llm_clients, test_dataset, temp_test_dir):
    """测试 workflow 的数据库记录功能"""
    
    code_llm, summary_llm = mock_llm_clients
    db_file = temp_test_dir / "test_workflow.db"
    
    from langchain_llm.models import LLM, OpenAILLMConfig
    
    # 测试用的 LLM 配置
    test_llm_config = {
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
    
    # 使用临时数据库
    with patch('simple_workflow.api.SimpleWorkflowSettings') as mock_settings_class:
        mock_settings = SimpleWorkflowSettings(
            enable_recording=True,
            database_url=f"sqlite:///{db_file}",
            llm_config=test_llm_config,
            code_llm="test_code_llm",
            summary_llm="test_summary_llm",
        )
        mock_settings_class.return_value = mock_settings
        
        with patch('langchain_llm.get_llm_client_by_model') as mock_get_llm:
            def get_mock_llm(model_config):
                if 'code' in str(model_config).lower():
                    return code_llm
                else:
                    return summary_llm
            
            mock_get_llm.side_effect = get_mock_llm
            
            result_json = await run_simple_workflow(
                init_program='def extract(article): return {}',
                data_path=test_dataset,
                target_accuracy=0.95,
                export_trace=True,
            )
    
    # 验证数据库文件已创建
    assert db_file.exists(), "数据库文件应该被创建"
    
    # 验证 trace 数据从数据库读取成功
    assert 'trace' in result_json.meta
    assert len(result_json.meta['trace']['iterations']) > 0
    
    print(f"✅ 数据库记录测试通过！")
    print(f"  - 数据库文件: {db_file}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
