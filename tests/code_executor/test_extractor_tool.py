import pytest
import json
from unittest.mock import Mock, MagicMock
from typing import Any, Dict, List
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage
from pydantic import BaseModel

from code_executor.tools.tool_defines.extractor_tool import ExtractTool


class MockLLM(BaseChatModel):
    """Mock LLM for testing ExtractTool"""
    
    mock_responses: Dict[str, Any] = {}
    call_count: int = 0
    last_messages: Any = None
    
    def __init__(self, mock_responses: Dict[str, Any] = None, **kwargs):
        super().__init__(**kwargs)
        self.mock_responses = mock_responses or {}
        self.call_count = 0
        self.last_messages = None
    
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        """Mock generation method"""
        self.call_count += 1
        self.last_messages = messages
        
        # 根据消息内容返回不同的响应
        user_message = str(messages[-1].content) if messages else ""
        
        # 根据内容匹配返回相应的 mock 响应
        for key, response in self.mock_responses.items():
            if key in user_message:
                return MagicMock(generations=[MagicMock(text=json.dumps(response))])
        
        # 默认响应
        return MagicMock(generations=[MagicMock(text='{"error": "no mock response found"}')])
    
    def invoke(self, input_data, config=None, **kwargs):
        """Mock invoke method"""
        self.call_count += 1
        
        # 处理不同类型的输入
        if hasattr(input_data, 'to_messages'):
            # ChatPromptValue 对象
            messages = input_data.to_messages()
        elif isinstance(input_data, list):
            messages = input_data
        elif isinstance(input_data, dict):
            messages = input_data.get('messages', [])
        else:
            messages = []
        
        self.last_messages = messages
        user_content = ""
        
        for msg in messages:
            if hasattr(msg, 'content'):
                user_content += str(msg.content)
        
        # 根据内容匹配返回相应的响应
        for key, response in self.mock_responses.items():
            if key in user_content:
                return AIMessage(content=json.dumps(response))
        
        # 默认响应
        return AIMessage(content='{"name": "Unknown", "age": 0}')
    
    @property
    def _llm_type(self) -> str:
        return "mock_llm"


class TestExtractTool:
    """ExtractTool 测试类"""
    
    def setup_method(self):
        """测试前设置"""
        self.mock_responses = {
            "John Doe": {"name": "John Doe", "age": 30, "city": "New York"},
            "String Null": {"name": "John Doe", "age": 30, "city": None},
            "products": {
                "products": [
                    {"name": "iPhone", "price": 999.99, "category": "Electronics"},
                    {"name": "MacBook", "price": 1299.99, "category": "Electronics"}
                ]
            },
            "company": {
                "name": "Tech Corp",
                "employees": [
                    {"name": "Alice", "position": "Engineer"},
                    {"name": "Bob", "position": "Designer"}
                ],
                "address": {"street": "123 Main St", "city": "San Francisco"}
            },
            "Tech Corp": {
                "name": "Tech Corp",
                "employees": [
                    {"name": "Alice", "position": "Engineer"},
                    {"name": "Bob", "position": "Designer"}
                ],
                "address": {"street": "123 Main St", "city": "San Francisco"}
            }
        }
        self.mock_llm = MockLLM(self.mock_responses)
        self.extractor = ExtractTool(self.mock_llm)

    
    def test_basic_extraction(self):
        """测试基本信息提取功能"""
        content = "John Doe is 30 years old and lives in New York."
        schema = {
            "type": "object",
            "title": "Person",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "city": {"type": "string"}
            },
            "required": ["name", "age"]
        }
        
        result = self.extractor(content, schema)
        
        assert isinstance(result, dict)
        assert "name" in result
        assert "age" in result
        assert result["name"] == "John Doe"
        assert result["age"] == 30
        assert result["city"] == "New York"
    
    def test_complex_schema(self):
        """测试复杂 schema 的提取"""
        content = "Our company Tech Corp has employees Alice (Engineer) and Bob (Designer)."
        schema = {
            "type": "object",
            "title": "Company",
            "properties": {
                "name": {"type": "string"},
                "employees": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "position": {"type": "string"}
                        }
                    }
                },
                "address": {
                    "type": "object",
                    "properties": {
                        "street": {"type": "string"},
                        "city": {"type": "string"}
                    }
                }
            }
        }
        
        result = self.extractor(content, schema)
        
        assert isinstance(result, dict)
        assert "name" in result
        assert "employees" in result
        assert isinstance(result["employees"], list)
        assert len(result["employees"]) == 2
        assert result["employees"][0]["name"] == "Alice"
        assert result["employees"][0]["position"] == "Engineer"
    
    def test_list_extraction(self):
        """测试列表类型数据提取"""
        # SchemaConverter 不支持数组类型，所以改为对象包装数组
        content = "We have iPhone for $999.99 and MacBook for $1299.99 in Electronics category."
        schema = {
            "type": "object",
            "title": "ProductList",
            "properties": {
                "products": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "price": {"type": "number"},
                            "category": {"type": "string"}
                        }
                    }
                }
            }
        }
        
        result = self.extractor(content, schema)
        
        assert isinstance(result, dict)
        assert "products" in result
        assert isinstance(result["products"], list)
        assert len(result["products"]) == 2
        assert result["products"][0]["name"] == "iPhone"
        assert result["products"][0]["price"] == 999.99
        assert result["products"][1]["name"] == "MacBook"
        assert result["products"][1]["price"] == 1299.99
    
    def test_nested_object_extraction(self):
        """测试嵌套对象提取"""
        content = "Tech Corp is located at 123 Main St, San Francisco with employees Alice and Bob."
        schema = {
            "type": "object",
            "title": "CompanyInfo",
            "properties": {
                "name": {"type": "string"},
                "employees": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "position": {"type": "string"}
                        }
                    }
                },
                "address": {
                    "type": "object",
                    "properties": {
                        "street": {"type": "string"},
                        "city": {"type": "string"}
                    }
                }
            }
        }
        
        result = self.extractor(content, schema)
        
        assert isinstance(result, dict)
        assert "address" in result
        assert isinstance(result["address"], dict)
        assert result["address"]["street"] == "123 Main St"
        assert result["address"]["city"] == "San Francisco"
    
    def test_missing_fields(self):
        """测试缺失字段处理"""
        # 设置一个返回部分字段的 mock 响应
        mock_llm = MockLLM({
            "incomplete": {"name": "John"}
        })
        extractor = ExtractTool(mock_llm)
        
        content = "This text has incomplete information about John."
        schema = {
            "type": "object",
            "title": "Person",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "city": {"type": "string"}
            },
            "required": ["name"]
        }
        
        result = extractor(content, schema)
        
        assert isinstance(result, dict)
        assert "name" in result
        assert result["name"] == "John"
        # 可选字段可能不存在
    
    def test_invalid_schema(self):
        """测试无效 schema 处理"""
        content = "Some content"
        invalid_schema = {
            "type": "invalid_type",
            "properties": {}
        }
        
        # 应该抛出异常或返回错误
        with pytest.raises(Exception):
            self.extractor(content, invalid_schema)
    
    def test_empty_content(self):
        """测试空内容处理"""
        mock_llm = MockLLM({
            "empty": {"name": "Empty", "age": 0}
        })
        extractor = ExtractTool(mock_llm)
        
        content = "empty"
        schema = {
            "type": "object",
            "title": "Person",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            }
        }
        
        result = extractor(content, schema)
        
        assert isinstance(result, dict)
        assert "name" in result
        assert "age" in result
    
    def test_llm_invocation(self):
        """测试 LLM 调用是否正确"""
        content = "Test content for LLM invocation"
        schema = {
            "type": "object",
            "title": "Test",
            "properties": {
                "test_field": {"type": "string"}
            }
        }
        
        self.extractor(content, schema)
        
        # 验证 LLM 被调用
        assert self.mock_llm.call_count > 0
        assert self.mock_llm.last_messages is not None
        
        # 验证传递给 LLM 的消息包含内容
        messages_content = str(self.mock_llm.last_messages)
        assert content in messages_content
    
    def test_schema_converter_integration(self):
        """测试与 SchemaConverter 的集成"""
        # 添加特定的 mock 响应
        mock_llm = MockLLM({
            "Integration": {"field1": "test_value", "field2": 42}
        })
        extractor = ExtractTool(mock_llm)
        
        content = "Integration test content"
        schema = {
            "type": "object",
            "title": "IntegrationTest",
            "properties": {
                "field1": {"type": "string"},
                "field2": {"type": "integer"}
            },
            "required": ["field1"]
        }
        
        # 这个测试主要验证 SchemaConverter.build() 能正常工作
        # 以及生成的 Pydantic 模型能正确解析
        result = extractor(content, schema)
        
        assert isinstance(result, dict)
        assert "field1" in result
        assert result["field1"] == "test_value"
        assert result["field2"] == 42
    
    def test_return_format(self):
        """测试返回格式"""
        content = "Format test content"
        schema = {
            "type": "object",
            "title": "FormatTest",
            "properties": {
                "test_field": {"type": "string"}
            }
        }
        
        result = self.extractor(content, schema)
        
        # 验证返回的是字典或列表（JSON 可序列化的格式）
        assert isinstance(result, (dict, list))
        
        # 验证可以序列化为 JSON
        json_str = json.dumps(result)
        assert isinstance(json_str, str)
        
        # 验证可以反序列化
        parsed = json.loads(json_str)
        assert parsed == result