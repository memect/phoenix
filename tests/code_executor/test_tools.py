import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any, List, Optional, Union
from typing_extensions import Annotated

# 导入被测试的模块
from code_executor.tools import (
    ToolRegistry, ToolDescriptor, ToolProxy, ToolHub, ToolHubFactory,
    PolicyContext, Policy, get_global_policy, create_default_tool_hub, create_tool_hub, 
    create_default_llm_guide, tool
)


# ===== 测试用工具类 =====

@tool(name='test_tool', methods=['process', 'validate'], description='测试工具')
class TestTool:
    """测试用工具类"""
    def __init__(self, config: str = 'default'):
        self.config = config
    
    def process(self, data: str) -> str:
        """处理数据"""
        return f"processed: {data} with {self.config}"
    
    def validate(self, value: int = 0) -> bool:
        """验证数值"""
        return value > 0
    
    def _private_method(self):
        """私有方法，不应该被检测到"""
        pass


@tool(name='calculator')
class Calculator:
    """计算器工具"""
    def __init__(self, precision: int = 2):
        self.precision = precision
    
    def add(self, a: int, b: int) -> int:
        """加法运算"""
        return a + b
    
    def multiply(self, a: int, b: int) -> int:
        """乘法运算"""
        return a * b


@tool(name='advanced_processor')
class AdvancedDataProcessor:
    """
    高级数据处理器工具
    
    这是一个复杂的数据处理工具，支持多种数据格式的处理、转换和分析。
    具有强大的数据验证、清洗和格式化功能。
    """
    
    def __init__(self, 
                 batch_size: int = 100, 
                 enable_cache: bool = True,
                 timeout: float = 30.0):
        """
        初始化高级数据处理器
        
        Args:
            batch_size: 批处理大小
            enable_cache: 是否启用缓存
            timeout: 处理超时时间（秒）
        """
        self.batch_size = batch_size
        self.enable_cache = enable_cache
        self.timeout = timeout
        self._cache = {} if enable_cache else None
    
    def process_data(self, 
                    data: Annotated[List[Dict[str, Any]], "输入数据列表，每个元素为字典格式"],
                    format_type: Annotated[str, "输出格式类型，支持 'json', 'csv', 'xml'"] = 'json',
                    filters: Optional[Dict[str, Any]] = None) -> Dict[str, Union[str, int, List]]:
        """
        处理输入数据并返回指定格式的结果
        
        Args:
            data: 输入数据列表，每个元素应为字典格式
            format_type: 输出格式类型，支持 'json', 'csv', 'xml'
            filters: 可选的过滤条件字典
            
        Returns:
            包含处理结果的字典，包含 'result', 'count', 'format' 等字段
            
        Raises:
            ValueError: 当输入数据格式不正确时
            TypeError: 当参数类型不匹配时
        """
        if not isinstance(data, list):
            raise TypeError("数据必须是列表格式")
        
        processed_count = 0
        filtered_data = []
        
        for item in data:
            if not isinstance(item, dict):
                continue
            
            # 应用过滤器
            if filters:
                if all(item.get(k) == v for k, v in filters.items()):
                    filtered_data.append(item)
                    processed_count += 1
            else:
                filtered_data.append(item)
                processed_count += 1
        
        return {
            'result': f"Processed {processed_count} items in {format_type} format",
            'count': processed_count,
            'format': format_type,
            'data': filtered_data[:5]  # 返回前5条作为示例
        }
    
    def validate_schema(self, 
                       data: Annotated[Dict[str, Any], "待验证的数据字典"],
                       schema: Annotated[Dict[str, type], "验证模式，键为字段名，值为期望类型"]) -> Dict[str, Union[bool, List[str]]]:
        """
        验证数据是否符合指定的模式
        
        Args:
            data: 待验证的数据字典
            schema: 验证模式，键为字段名，值为期望的数据类型
            
        Returns:
            验证结果字典，包含 'valid' 布尔值和 'errors' 错误列表
        """
        errors = []
        
        for field, expected_type in schema.items():
            if field not in data:
                errors.append(f"缺少必需字段: {field}")
            elif not isinstance(data[field], expected_type):
                errors.append(f"字段 {field} 类型错误，期望 {expected_type.__name__}，实际 {type(data[field]).__name__}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def transform_data(self, 
                      source_data: Annotated[List[Dict], "源数据列表"],
                      mapping: Annotated[Dict[str, str], "字段映射关系，键为源字段名，值为目标字段名"],
                      default_values: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        根据映射关系转换数据结构
        
        Args:
            source_data: 源数据列表
            mapping: 字段映射关系字典
            default_values: 默认值字典，用于填充缺失字段
            
        Returns:
            转换后的数据列表
        """
        transformed = []
        default_values = default_values or {}
        
        for item in source_data:
            new_item = {}
            
            # 应用字段映射
            for source_field, target_field in mapping.items():
                if source_field in item:
                    new_item[target_field] = item[source_field]
                elif target_field in default_values:
                    new_item[target_field] = default_values[target_field]
            
            # 添加默认值中未映射的字段
            for field, value in default_values.items():
                if field not in new_item:
                    new_item[field] = value
            
            transformed.append(new_item)
        
        return transformed
    
    def aggregate_data(self, 
                      data: Annotated[List[Dict[str, Union[int, float]]], "数值数据列表"],
                      group_by: Annotated[str, "分组字段名"],
                      agg_fields: Annotated[List[str], "需要聚合的数值字段列表"]) -> Dict[str, Dict[str, float]]:
        """
        对数据进行分组聚合计算
        
        Args:
            data: 包含数值的数据列表
            group_by: 用于分组的字段名
            agg_fields: 需要进行聚合计算的数值字段列表
            
        Returns:
            聚合结果字典，按分组值组织，每组包含各字段的统计信息
        """
        groups = {}
        
        # 分组数据
        for item in data:
            group_key = str(item.get(group_by, 'unknown'))
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(item)
        
        # 计算聚合统计
        result = {}
        for group_key, group_data in groups.items():
            group_stats = {}
            
            for field in agg_fields:
                values = [item.get(field, 0) for item in group_data if isinstance(item.get(field), (int, float))]
                if values:
                    group_stats[field] = {
                        'sum': sum(values),
                        'avg': sum(values) / len(values),
                        'min': min(values),
                        'max': max(values),
                        'count': len(values)
                    }
                else:
                    group_stats[field] = {'sum': 0, 'avg': 0, 'min': 0, 'max': 0, 'count': 0}
            
            result[group_key] = group_stats
        
        return result


# ===== 测试类 =====

class TestToolRegistry:
    """测试工具注册中心"""
    
    def test_tool_decorator_registration(self):
        """测试@tool装饰器注册功能"""
        # 验证工具已正确注册
        assert 'test_tool' in ToolRegistry.list_tools()
        assert 'calculator' in ToolRegistry.list_tools()
        
        # 验证描述器信息
        descriptor = ToolRegistry.get_descriptor('test_tool')
        assert descriptor is not None
        assert descriptor.tool_class == TestTool
        assert 'process' in descriptor.methods
        assert 'validate' in descriptor.methods
        assert '_private_method' not in descriptor.methods
    
    def test_create_instance_with_args_kwargs(self):
        """测试create_instance方法的参数传递"""
        # 测试无参数创建
        instance1 = ToolRegistry.create_instance('test_tool')
        assert isinstance(instance1, TestTool)
        assert instance1.config == 'default'
        
        # 测试带kwargs创建
        instance2 = ToolRegistry.create_instance(
            'test_tool', 
            kwargs={'config': 'custom'}
        )
        assert instance2.config == 'custom'
        
        # 测试带args创建
        instance3 = ToolRegistry.create_instance(
            'test_tool',
            args=['from_args']
        )
        assert instance3.config == 'from_args'
    
    def test_list_tools_and_get_descriptor(self):
        """测试工具列表获取和描述器获取"""
        tools = ToolRegistry.list_tools()
        assert isinstance(tools, list)
        assert 'test_tool' in tools
        assert 'calculator' in tools
        
        # 测试获取存在的描述器
        descriptor = ToolRegistry.get_descriptor('test_tool')
        assert descriptor is not None
        assert isinstance(descriptor, ToolDescriptor)
        
        # 测试获取不存在的描述器
        with pytest.raises(ValueError):
            ToolRegistry.get_descriptor('nonexistent')
    
    def test_get_tool_guide(self):
        """测试工具指南生成"""
        guide = ToolRegistry.get_tool_guide('test_tool')
        assert guide is not None
        assert 'TestTool' in guide
        assert 'process' in guide
        assert 'validate' in guide
        
        # 测试不存在工具的指南
        with pytest.raises(ValueError):
            ToolRegistry.get_tool_guide('nonexistent')
    
    def test_create_instance_error_handling(self):
        """测试创建实例的错误处理"""
        with pytest.raises(ValueError, match="Tool 'nonexistent' not registered"):
            ToolRegistry.create_instance('nonexistent')
    
    def test_get_all_tool_guides(self):
        """测试一次性生成多个工具的指南"""
        # 获取所有工具的指南
        all_guides = ToolRegistry.get_all_tools_guide()
        
        # 验证返回的是字符串
        assert isinstance(all_guides, str)
        assert len(all_guides) > 0
        
        # 验证包含已注册的工具
        registered_tools = ToolRegistry.list_tools()
        assert len(registered_tools) >= 2  # 至少有test_tool和calculator
        
        # 验证每个已注册工具都在指南中
        for tool_name in registered_tools:
            assert tool_name in all_guides, f"工具 {tool_name} 应该在总指南中"
        
        # 验证指南格式正确
        assert '# test_tool' in all_guides or 'TestTool' in all_guides
        assert '# calculator' in all_guides or 'Calculator' in all_guides
        
        # 验证包含分隔符
        assert '---' in all_guides
        
        # 验证包含方法信息
        assert 'process' in all_guides  # TestTool的方法
        assert 'add' in all_guides      # Calculator的方法
        
        # 测试空注册表的情况（通过临时清空来测试）
        original_descriptors = ToolRegistry._descriptors.copy()
        try:
            ToolRegistry._descriptors.clear()
            empty_guide = ToolRegistry.get_all_tools_guide()
            assert empty_guide == ""
        finally:
            # 恢复原始注册表
            ToolRegistry._descriptors.update(original_descriptors)
        
        # 验证恢复后功能正常
        restored_guides = ToolRegistry.get_all_tools_guide()
        assert len(restored_guides) > 0
        assert 'test_tool' in restored_guides or 'TestTool' in restored_guides


class TestToolDescriptor:
    """测试工具描述器"""
    
    def test_auto_detect_methods(self):
        """测试自动方法检测"""
        descriptor = ToolDescriptor(TestTool)
        methods = descriptor.methods
        
        # 验证检测到公共方法
        assert 'process' in methods
        assert 'validate' in methods
        
        # 验证排除私有方法
        assert '_private_method' not in methods
        assert '__init__' not in methods
    
    def test_generate_llm_guide(self):
        """测试LLM指南生成"""
        descriptor = ToolDescriptor(
            TestTool, 
            methods=['process', 'validate'],
            description='测试工具描述'
        )
        
        guide = descriptor.generate_llm_guide()
        assert '## TestTool' in guide
        assert '测试工具描述' in guide
        assert '### 可用方法:' in guide
        assert 'process' in guide
        assert 'validate' in guide
    
    def test_method_guide_with_annotations(self):
        """测试带类型注解的方法指南生成"""
        descriptor = ToolDescriptor(Calculator, methods=['add'])
        guide = descriptor.generate_llm_guide()
        
        # 验证方法签名包含类型注解
        assert 'add(' in guide
        assert 'int' in guide
    
    def test_complex_tool_descriptor_generation(self):
        """测试复杂工具类的描述器生成功能"""
        # 测试复杂工具类的自动方法检测
        descriptor = ToolDescriptor(AdvancedDataProcessor)
        methods = descriptor.methods
        
        # 验证检测到所有公共方法
        expected_methods = ['process_data', 'validate_schema', 'transform_data', 'aggregate_data']
        for method in expected_methods:
            assert method in methods, f"方法 {method} 应该被检测到"
        
        # 验证排除私有方法和特殊方法
        assert '__init__' not in methods
        assert '_cache' not in methods
        
        # 测试类描述解析
        descriptor_with_desc = ToolDescriptor(
            AdvancedDataProcessor, 
            description='高级数据处理工具'
        )
        guide = descriptor_with_desc.generate_llm_guide()
        
        # 验证类名和描述
        assert '## AdvancedDataProcessor' in guide
        assert '高级数据处理工具' in guide
        
        # 验证方法签名解析（包括Annotated类型）
        assert 'process_data(' in guide
        assert 'validate_schema(' in guide
        assert 'transform_data(' in guide
        assert 'aggregate_data(' in guide
        
        # 验证Annotated类型注释的处理
        assert 'List[Dict[str, Any]]' in guide or 'data:' in guide
        assert 'Dict[str, Any]' in guide or 'schema:' in guide
        
        # 验证方法文档字符串包含在指南中
        assert '处理输入数据并返回指定格式的结果' in guide
        assert '验证数据是否符合指定的模式' in guide
        assert '根据映射关系转换数据结构' in guide
        assert '对数据进行分组聚合计算' in guide
        
        # 测试指定特定方法的描述器
        specific_descriptor = ToolDescriptor(
            AdvancedDataProcessor, 
            methods=['process_data', 'validate_schema']
        )
        specific_guide = specific_descriptor.generate_llm_guide()
        
        # 验证只包含指定的方法
        assert 'process_data(' in specific_guide
        assert 'validate_schema(' in specific_guide
        assert 'transform_data(' not in specific_guide
        assert 'aggregate_data(' not in specific_guide
        
        # 测试复杂参数类型的处理
        # 验证Optional类型的处理
        assert 'Optional' in guide or 'filters:' in guide
        
        # 验证Union类型的处理
        assert 'Union' in guide or 'Dict[str, Union[' in guide
        
        # 验证返回类型注释
        assert 'Dict[str' in guide  # 返回类型应该包含Dict相关信息
        
        # 测试方法数量验证
        assert len(descriptor.methods) == 4, "应该检测到4个公共方法"
        
        # 测试类级别docstring的处理
        class_guide = descriptor.generate_llm_guide()
        assert '高级数据处理器工具' in class_guide
        assert '支持多种数据格式的处理、转换和分析' in class_guide
        
        # 验证方法参数的详细文档
        assert 'Args:' in guide  # 参数文档应该被包含
        assert 'Returns:' in guide  # 返回值文档应该被包含
        assert 'Raises:' in guide  # 异常文档应该被包含（如果存在）


class TestPolicyContext:
    """测试策略上下文管理器"""
    
    def test_context_manager_basic(self):
        """测试基本上下文管理器功能"""
        policy = Policy(
            tool_names=['test_tool'],
            tool_config={'test_tool': {'kwargs': {'config': 'context_test'}}}
        )
        
        # 测试上下文外的默认策略
        default_policy = get_global_policy()
        assert default_policy.tool_names == []
        
        # 测试上下文内的策略
        with PolicyContext(policy):
            current_policy = get_global_policy()
            assert current_policy.tool_names == ['test_tool']
            assert current_policy.tool_config == policy.tool_config
        
        # 测试退出上下文后恢复
        restored_policy = get_global_policy()
        assert restored_policy.tool_names == []
    
    def test_nested_context(self):
        """测试嵌套上下文"""
        policy1 = Policy(tool_names=['tool1'], tool_config={})
        policy2 = Policy(tool_names=['tool2'], tool_config={})
        
        with PolicyContext(policy1):
            assert get_global_policy().tool_names == ['tool1']
            
            with PolicyContext(policy2):
                assert get_global_policy().tool_names == ['tool2']
            
            # 内层退出后恢复外层
            assert get_global_policy().tool_names == ['tool1']
        
        # 全部退出后恢复默认
        assert get_global_policy().tool_names == []
    
    def test_exception_handling_in_context(self):
        """测试上下文中异常处理"""
        policy = Policy(tool_names=['test_tool'], tool_config={})
        
        try:
            with PolicyContext(policy):
                assert get_global_policy().tool_names == ['test_tool']
                raise ValueError("测试异常")
        except ValueError:
            pass
        
        # 异常后策略应该正确恢复
        assert get_global_policy().tool_names == []
    
    def test_get_current_policy(self):
        """测试获取当前策略"""
        policy = Policy(tool_names=['test_tool'], tool_config={})
        
        with PolicyContext(policy) as ctx:
            current = ctx.get_current_policy()
            assert current.tool_names == ['test_tool']


class TestToolHub:
    """测试工具中心"""
    
    def test_create_tool_hub_basic(self):
        """测试基本ToolHub创建"""
        tool_config = {
            'test_tool': {
                'kwargs': {'config': 'hub_test'}
            }
        }
        
        hub = create_tool_hub(['test_tool'], tool_config)
        assert isinstance(hub, ToolHub)
        assert 'test_tool' in hub.list_tools()
    
    def test_get_tool_and_method_visibility(self):
        """测试工具获取和方法可见性"""
        tool_config = {
            'test_tool': {
                'kwargs': {'config': 'visibility_test'}
            }
        }
        
        hub = create_tool_hub(['test_tool'], tool_config)
        tool_proxy = hub.get_tool('test_tool')
        
        # 测试可以访问允许的方法
        result = tool_proxy.process('test_data')
        assert 'processed: test_data with visibility_test' in result
        
        # 测试不能访问私有方法
        with pytest.raises(AttributeError):
            tool_proxy._private_method()
    
    def test_tool_config_validation(self):
        """测试工具配置验证"""
        factory = ToolHubFactory()
        
        # 测试缺少工具配置
        with pytest.raises(ValueError, match="Missing configuration for tool"):
            factory.create_tool_hub(['test_tool'], {})
        
        # 测试args不是list类型
        with pytest.raises(TypeError, match="'args' field.*must be a list"):
            factory.create_tool_hub(
                ['test_tool'], 
                {'test_tool': {'args': 'not_a_list'}}
            )
        
        # 测试kwargs不是dict类型
        with pytest.raises(TypeError, match="'kwargs' field.*must be a dictionary"):
            factory.create_tool_hub(
                ['test_tool'], 
                {'test_tool': {'kwargs': 'not_a_dict'}}
            )
        
        # 测试未知字段
        with pytest.raises(ValueError, match="Unknown fields"):
            factory.create_tool_hub(
                ['test_tool'], 
                {'test_tool': {'unknown_field': 'value'}}
            )
    
    def test_tool_hub_guide_generation(self):
        """测试ToolHub指南生成"""
        tool_config = {'test_tool': {}}
        hub = create_tool_hub(['test_tool'], tool_config)
        
        guide = hub.get_tool_guide()
        assert 'get_tool' in guide
        assert 'test_tool' in guide
        assert 'code-tool-description' in guide


class TestIntegration:
    """测试集成功能"""
    
    def test_full_workflow(self):
        """测试完整工作流程"""
        # 1. 创建策略
        policy = Policy(
            tool_names=['test_tool', 'calculator'],
            tool_config={
                'test_tool': {'kwargs': {'config': 'workflow_test'}},
                'calculator': {'kwargs': {'precision': 3}}
            }
        )
        
        # 2. 使用PolicyContext
        with PolicyContext(policy):
            # 3. 创建默认ToolHub
            hub = create_default_tool_hub()
            
            # 4. 获取并使用工具
            test_tool = hub.get_tool('test_tool')
            calc_tool = hub.get_tool('calculator')
            
            # 5. 验证工具功能
            result1 = test_tool.process('integration_data')
            assert 'workflow_test' in result1
            
            result2 = calc_tool.add(5, 3)
            assert result2 == 8
    
    @patch('code_executor.tools.ExtractTool.__call__')
    def test_extract_tool_integration(self, mock_extract):
        """测试ExtractTool集成"""
        # Mock ExtractTool的调用
        mock_extract.return_value = {'extracted': 'data'}
        
        # 验证ExtractTool已注册
        assert 'extract' in ToolRegistry.list_tools()
        
        # 创建包含ExtractTool的ToolHub
        mock_llm = Mock()
        tool_config = {
            'extract': {
                'args': [mock_llm]
            }
        }
        
        hub = create_tool_hub(['extract'], tool_config)
        extract_tool = hub.get_tool('extract')
        
        # 调用工具
        result = extract_tool('test content', {'field': 'string'})
        assert result == {'extracted': 'data'}
        mock_extract.assert_called_once()
    
    def test_create_default_tool_hub_with_context(self):
        """测试在上下文中创建默认ToolHub"""
        policy = Policy(
            tool_names=['calculator'],
            tool_config={'calculator': {}}
        )
        
        # 在上下文外创建
        default_hub1 = create_default_tool_hub()
        assert default_hub1.list_tools() == []
        
        # 在上下文内创建
        with PolicyContext(policy):
            default_hub2 = create_default_tool_hub()
            assert 'calculator' in default_hub2.list_tools()
    
    def test_tool_isolation(self):
        """测试工具实例隔离"""
        tool_config = {
            'test_tool': {'kwargs': {'config': 'instance1'}}
        }
        
        # 创建两个ToolHub
        hub1 = create_tool_hub(['test_tool'], tool_config)
        hub2 = create_tool_hub(['test_tool'], tool_config)
        
        tool1 = hub1.get_tool('test_tool')
        tool2 = hub2.get_tool('test_tool')
        
        # 验证是不同的实例
        assert tool1 is not tool2
        
        # 但功能相同
        result1 = tool1.process('test')
        result2 = tool2.process('test')
        assert result1 == result2
    
    def test_create_default_llm_guide(self):
        """测试 create_default_llm_guide() 函数"""
        # 测试空策略情况（无工具配置）
        empty_guide = create_default_llm_guide()
        
        # 验证基本结构存在
        assert isinstance(empty_guide, str)
        assert '<tool-import-guide>' in empty_guide
        assert '</tool-import-guide>' in empty_guide
        assert '<available-tools>' in empty_guide
        assert '</available-tools>' in empty_guide
        assert '<tool-details>' in empty_guide
        assert '</tool-details>' in empty_guide
        
        # 验证导入说明
        assert 'from code_executor.document.models.document import Document' in empty_guide
        assert 'from code_executor.tools import ToolHub' in empty_guide
        assert 'tool_hub.get_tool(' in empty_guide
        
        # 空策略应该显示无可用工具
        assert '当前策略未配置任何工具' in empty_guide
        
        # 测试单个工具策略
        single_tool_policy = Policy(
            tool_names=['test_tool'],
            tool_config={'test_tool': {'kwargs': {'config': 'guide_test'}}}
        )
        
        with PolicyContext(single_tool_policy):
            single_guide = create_default_llm_guide()
            
            # 验证包含工具信息
            assert 'test_tool' in single_guide
            assert 'TestTool' in single_guide
            assert 'process' in single_guide
            assert 'validate' in single_guide
            
            # 验证代码示例
            assert "tool = tool_hub.get_tool('test_tool')" in single_guide
            
        # 测试多个工具策略
        multi_tool_policy = Policy(
            tool_names=['test_tool', 'calculator'],
            tool_config={
                'test_tool': {'kwargs': {'config': 'multi_test'}},
                'calculator': {'kwargs': {'precision': 2}}
            }
        )
        
        with PolicyContext(multi_tool_policy):
            multi_guide = create_default_llm_guide()
            
            # 验证包含所有工具
            assert 'test_tool' in multi_guide
            assert 'calculator' in multi_guide
            assert 'TestTool' in multi_guide
            assert 'Calculator' in multi_guide
            
            # 验证包含各工具的方法
            assert 'process' in multi_guide  # TestTool的方法
            assert 'add' in multi_guide      # Calculator的方法
            assert 'multiply' in multi_guide # Calculator的方法
            
            # 验证工具列表格式
            assert '- **test_tool**:' in multi_guide
            assert '- **calculator**:' in multi_guide
            
            # 验证代码示例包含多个工具
            assert "tool_hub.get_tool('test_tool')" in multi_guide
            assert "tool_hub.get_tool('calculator')" in multi_guide
        
        # 测试XML标签结构完整性
        test_policy = Policy(
            tool_names=['test_tool'],
            tool_config={'test_tool': {}}
        )
        
        with PolicyContext(test_policy):
            guide = create_default_llm_guide()
            
            # 验证所有XML标签都有开始和结束标签
            xml_tags = ['tool-import-guide', 'available-tools', 'tool-details']
            for tag in xml_tags:
                assert f'<{tag}>' in guide, f"缺少开始标签 <{tag}>"
                assert f'</{tag}>' in guide, f"缺少结束标签 </{tag}>"
            
            # 验证Markdown格式
            assert '# 工具导入和使用指南' in guide
            assert '## 推荐入口' in guide
            assert '## 基本用法' in guide
            assert '# 可用工具列表' in guide
            assert '# 工具详细说明' in guide
            
            # 验证代码块格式
            assert '```python' in guide
            assert '```' in guide
            
            # 验证包含使用示例和注意事项
            assert '注意事项' in guide or '重要提示' in guide
        
        # 测试嵌套策略上下文
        outer_policy = Policy(
            tool_names=['calculator'],
            tool_config={'calculator': {}}
        )
        inner_policy = Policy(
            tool_names=['test_tool'],
            tool_config={'test_tool': {}}
        )
        
        with PolicyContext(outer_policy):
            outer_guide = create_default_llm_guide()
            assert 'calculator' in outer_guide
            assert 'test_tool' not in outer_guide
            
            with PolicyContext(inner_policy):
                inner_guide = create_default_llm_guide()
                assert 'test_tool' in inner_guide
                assert 'calculator' not in inner_guide
            
            # 退出内层上下文后，应该恢复外层策略
            restored_guide = create_default_llm_guide()
            assert 'calculator' in restored_guide
            assert 'test_tool' not in restored_guide


class TestToolProxy:
    """测试工具代理"""
    
    def test_method_access_control(self):
        """测试方法访问控制"""
        tool_instance = TestTool('proxy_test')
        proxy = ToolProxy(tool_instance, ['process'])
        
        # 可以访问允许的方法
        result = proxy.process('test_data')
        assert 'processed: test_data' in result
        
        # 不能访问不允许的方法
        with pytest.raises(AttributeError, match="Method 'validate' is not available"):
            proxy.validate(5)
    
    def test_dir_method(self):
        """测试__dir__方法"""
        tool_instance = TestTool()
        proxy = ToolProxy(tool_instance, ['process', 'validate'])
        
        available_methods = dir(proxy)
        assert 'process' in available_methods
        assert 'validate' in available_methods
        assert len(available_methods) == 2


class TestPolicy:
    """测试策略类"""
    
    def test_policy_properties(self):
        """测试策略属性"""
        policy = Policy(
            tool_names=['tool1', 'tool2'],
            tool_config={'tool1': {}, 'tool2': {}}
        )
        
        assert policy.tool_names == ['tool1', 'tool2']
        assert policy.tool_config == {'tool1': {}, 'tool2': {}}
        
        # 测试属性设置
        policy.tool_names = ['tool3']
        policy.tool_config = {'tool3': {}}
        
        assert policy.tool_names == ['tool3']
        assert policy.tool_config == {'tool3': {}}
    
    def test_policy_clear(self):
        """测试策略清空"""
        policy = Policy(
            tool_names=['tool1'],
            tool_config={'tool1': {}}
        )
        
        policy.clear()
        assert policy.tool_names == []
        assert policy.tool_config == {}


if __name__ == '__main__':
    pytest.main([__file__])
