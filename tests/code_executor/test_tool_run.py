import pytest
import asyncio
from unittest.mock import Mock, patch
from code_executor.executor import do_extract
from code_executor.tools import PolicyContext, Policy


class TestToolRunInDynamicExecution:
    """测试工具调用在 do_extract 动态执行环境中的功能"""
    
    def setup_method(self):
        """测试前准备"""
        # 创建 Mock LLM 实例
        self.mock_llm = Mock()
        self.mock_llm.invoke.return_value = Mock(content='{"name": "测试结果", "value": 42}')
        
        # 测试数据
        self.test_data = {
            'content': '这是一个测试文档，包含姓名：张三，年龄：25岁',
            'schema': {
                'title': 'PersonInfo',
                'type': 'object',
                'properties': {
                    'name': {'type': 'string', 'description': '姓名'},
                    'age': {'type': 'integer', 'description': '年龄'}
                },
                'required': ['name', 'age']
            }
        }
    
    @pytest.mark.asyncio
    async def test_basic_tool_import_and_creation(self):
        """测试基本工具导入和创建"""
        program_code = """
from code_executor import create_default_tool_hub

def extract(data):
    # 创建工具中心
    tool_hub = create_default_tool_hub()
    
    # 验证工具中心创建成功
    assert tool_hub is not None
    
    # 获取可用工具列表
    tools = tool_hub.list_tools()
    
    return {
        'success': True,
        'tools_count': len(tools),
        'available_tools': tools
    }
"""
        
        # 设置测试策略
        test_policy = Policy(
            tool_names=['extract'],
            tool_config={
                'extract': {
                    'args': [self.mock_llm],
                    'kwargs': {}
                }
            }
        )
        
        with PolicyContext(test_policy):
            result = await do_extract(program_code, self.test_data)
            
            assert result['success'] is True
            assert result['tools_count'] >= 0
            assert isinstance(result['available_tools'], list)
    
    @pytest.mark.asyncio
    async def test_tool_calling_functionality(self):
        """测试工具调用功能"""
        program_code = """
from code_executor import create_default_tool_hub

def extract(data):
    # 创建工具中心
    tool_hub = create_default_tool_hub()
    
    # 获取提取工具
    extract_tool = tool_hub.get_tool('extract')
    
    if extract_tool is None:
        return {'error': 'Extract tool not found'}
    
    # 调用工具进行提取
    try:
        result = extract_tool(data['content'], data['schema'])
        return {
            'success': True,
            'extracted_data': result,
            'tool_called': True
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'tool_called': True
        }
"""
        
        # 设置测试策略
        test_policy = Policy(
            tool_names=['extract'],
            tool_config={
                'extract': {
                    'args': [self.mock_llm],
                    'kwargs': {}
                }
            }
        )
        
        with patch('langchain_core.output_parsers.PydanticOutputParser') as mock_parser:
            # Mock 解析器返回结果
            mock_parser_instance = Mock()
            mock_parser_instance.invoke.return_value = {'name': '张三', 'age': 25}
            mock_parser.return_value = mock_parser_instance
            
            with PolicyContext(test_policy):
                    result = await do_extract(program_code, self.test_data)
                    
                    # 如果失败，在断言中包含错误信息
                    assert result['success'] is True, f"Tool calling failed with error: {result.get('error', 'Unknown error')}"
                    assert result['tool_called'] is True
                    assert 'extracted_data' in result
    
    @pytest.mark.asyncio
    async def test_policy_context_transmission(self):
        """测试策略上下文传递"""
        program_code = """
from code_executor import create_default_tool_hub
from code_executor.tools import get_global_policy

def extract(data):
    # 获取当前策略
    current_policy = get_global_policy()
    
    # 创建工具中心
    tool_hub = create_default_tool_hub()
    
    return {
        'policy_tool_names': current_policy.tool_names,
        'policy_config_keys': list(current_policy.tool_config.keys()),
        'hub_tools': tool_hub.list_tools()
    }
"""
        
        # 设置测试策略
        test_policy = Policy(
            tool_names=['extract'],
            tool_config={
                'extract': {
                    'args': [self.mock_llm],
                    'kwargs': {}
                }
            }
        )
        
        with PolicyContext(test_policy):
            result = await do_extract(program_code, self.test_data)
            
            # 验证策略正确传递
            assert 'extract' in result['policy_tool_names']
            assert 'extract' in result['policy_config_keys']
    
    @pytest.mark.asyncio
    async def test_tool_not_found_error_handling(self):
        """测试工具不存在的错误处理"""
        program_code = """
from code_executor import create_default_tool_hub

def extract(data):
    # 创建工具中心
    tool_hub = create_default_tool_hub()
    
    # 尝试获取不存在的工具
    nonexistent_tool = tool_hub.get_tool('nonexistent_tool')
    
    return {
        'tool_found': nonexistent_tool is not None,
        'tool_value': nonexistent_tool
    }
"""
        
        # 设置空策略
        test_policy = Policy(tool_names=[], tool_config={})
        
        with PolicyContext(test_policy):
            result = await do_extract(program_code, self.test_data)
            
            assert result['tool_found'] is False
            assert result['tool_value'] is None
    
    @pytest.mark.asyncio
    async def test_empty_policy_handling(self):
        """测试空策略处理"""
        program_code = """
from code_executor import create_default_tool_hub
from code_executor.tools import get_global_policy

def extract(data):
    # 获取当前策略
    current_policy = get_global_policy()
    
    # 创建工具中心
    tool_hub = create_default_tool_hub()
    
    return {
        'policy_is_empty': len(current_policy.tool_names) == 0,
        'available_tools': tool_hub.list_tools(),
        'tools_count': len(tool_hub.list_tools())
    }
"""
        
        # 设置空策略
        test_policy = Policy(tool_names=[], tool_config={})
        
        with PolicyContext(test_policy):
            result = await do_extract(program_code, self.test_data)
            
            assert result['policy_is_empty'] is True
            assert result['tools_count'] == 0
            assert result['available_tools'] == []
    
    @pytest.mark.asyncio
    async def test_multiple_tools_usage(self):
        """测试多个工具的使用"""
        program_code = """
from code_executor import create_default_tool_hub

def extract(data):
    # 创建工具中心
    tool_hub = create_default_tool_hub()
    
    results = {}
    
    # 尝试获取工具（包括存在和不存在的）
    for tool_name in ['extract', 'nonexistent_tool']:
        tool = tool_hub.get_tool(tool_name)
        results[tool_name] = {
            'available': tool is not None,
            'type': str(type(tool)) if tool else None
        }
    
    return {
        'tools_results': results,
        'total_available_tools': len([name for name, info in results.items() if info['available']])
    }
"""
        
        # 设置单工具策略
        test_policy = Policy(
            tool_names=['extract'],
            tool_config={
                'extract': {
                    'args': [self.mock_llm],
                    'kwargs': {}
                }
            }
        )
        
        with PolicyContext(test_policy):
            result = await do_extract(program_code, self.test_data)
            
            assert result['total_available_tools'] == 1
            assert 'extract' in result['tools_results']
            assert result['tools_results']['extract']['available'] is True
            assert result['tools_results']['nonexistent_tool']['available'] is False
    
    @pytest.mark.asyncio
    async def test_nested_policy_context(self):
        """测试嵌套策略上下文"""
        program_code = """
from code_executor import create_default_tool_hub
from code_executor.tools import get_global_policy, PolicyContext, Policy

def extract(data):
    # 获取外层策略
    outer_policy = get_global_policy()
    outer_tools = outer_policy.tool_names.copy()
    
    # 创建内层策略（空策略）
    inner_policy = Policy(
        tool_names=[],
        tool_config={}
    )
    
    with PolicyContext(inner_policy):
        inner_current_policy = get_global_policy()
        inner_tools = inner_current_policy.tool_names.copy()
        
        # 在内层创建工具中心
        inner_tool_hub = create_default_tool_hub()
        inner_available = inner_tool_hub.list_tools()
    
    # 回到外层
    final_policy = get_global_policy()
    final_tools = final_policy.tool_names.copy()
    
    return {
        'outer_tools': outer_tools,
        'inner_tools': inner_tools,
        'inner_available': inner_available,
        'final_tools': final_tools,
        'context_restored': outer_tools == final_tools
    }
"""
        
        # 设置外层策略
        test_policy = Policy(
            tool_names=['extract'],
            tool_config={
                'extract': {
                    'args': [self.mock_llm],
                    'kwargs': {}
                }
            }
        )
        
        with PolicyContext(test_policy):
            result = await do_extract(program_code, self.test_data)
            
            assert 'extract' in result['outer_tools']
            assert len(result['inner_tools']) == 0  # 内层是空策略
            assert len(result['inner_available']) == 0  # 内层无可用工具
            assert result['context_restored'] is True
    
    @pytest.mark.asyncio
    async def test_import_error_handling(self):
        """测试导入错误处理"""
        program_code = """
# 故意使用错误的导入路径
try:
    from code_executor.nonexistent_module import create_default_tool_hub
    import_success = True
    error_message = None
except ImportError as e:
    import_success = False
    error_message = str(e)

def extract(data):
    return {
        'import_success': import_success,
        'error_message': error_message
    }
"""
        
        test_policy = Policy(tool_names=[], tool_config={})
        
        with PolicyContext(test_policy):
            result = await do_extract(program_code, self.test_data)
            
            assert result['import_success'] is False
            assert 'nonexistent_module' in result['error_message']
