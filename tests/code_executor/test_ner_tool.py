"""ExtractTool (NER工具) 的测试模块

这个模块包含了对 code_executor.tools.tool_defines.ner_tool.NerTool 
的全面测试用例，覆盖了以下测试场景：

1. 基础功能测试：
   - 工具初始化
   - 正常的NER调用
   - 空内容处理

2. 不同类型文本测试：
   - 中文文本处理
   - 财务相关实体识别
   - 特殊字符处理

3. 错误处理测试：
   - HTTP请求错误
   - 无效JSON响应

4. 参数化测试：
   - 各种输入参数的测试

测试使用了Mock对象来模拟HTTP请求，避免对实际NER服务的依赖。
"""

import pytest
import httpx
import sys
import os
from unittest.mock import Mock, patch

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from code_executor.tools.tool_defines.ner_tool import NerTool


class TestExtractTool:
    """ExtractTool（NER工具）的测试类"""
    
    def setup_method(self):
        """测试前的设置"""
        self.test_url = "http://localhost:8080/ner"
        self.ner_tool = NerTool(url=self.test_url)
    
    def test_init(self):
        """测试ExtractTool初始化"""
        tool = NerTool("http://test.com/ner")
        assert tool.url == "http://test.com/ner"
    
    @patch('httpx.request')
    def test_call_success(self, mock_request):
        """测试成功调用NER服务"""
        # 模拟成功的HTTP响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "Result": {
                "ori_text": "腾讯、字节跳动等公司宣布捐款1亿元。",
                "ner_result": [
                    ["腾讯", "ORG", [0, 2]],
                    ["字节跳动", "ORG", [3, 7]],
                    ["1亿元", "AMOUNT", [14, 17]]
                ]
            }
        }
        mock_request.return_value = mock_response
        
        # 测试调用
        content = "腾讯、字节跳动等公司宣布捐款1亿元。"
        result = self.ner_tool(content)
        
        # 验证请求参数
        mock_request.assert_called_once_with(
            "POST",
            self.test_url,
            headers={'Content-Type': 'application/json'},
            json={'data': content}
        )
        
        # 验证返回结果
        assert result["ori_text"] == content
        assert len(result["ner_result"]) == 3
        assert result["ner_result"][0] == ["腾讯", "ORG", [0, 2]]
    
    @patch('httpx.request')
    def test_call_empty_content(self, mock_request):
        """测试空内容输入"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "Result": {
                "ori_text": "",
                "ner_result": []
            }
        }
        mock_request.return_value = mock_response
        
        result = self.ner_tool("")
        
        mock_request.assert_called_once_with(
            "POST",
            self.test_url,
            headers={'Content-Type': 'application/json'},
            json={'data': ""}
        )
        
        assert result["ori_text"] == ""
        assert result["ner_result"] == []
    
    @patch('httpx.request')
    def test_request_error(self, mock_request):
        """测试HTTP请求错误"""
        mock_request.side_effect = httpx.RequestError("Connection failed")
        
        with pytest.raises(httpx.RequestError):
            self.ner_tool("测试文本")
    
    @patch('httpx.request')
    def test_call_chinese_text(self, mock_request):
        """测试中文文本处理"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "Result": {
                "ori_text": "邓小平同志在北京会见了文因互联有限公司的代表。",
                "ner_result": [
                    ["邓小平", "PER", [0, 3]],
                    ["北京", "LOC", [6, 8]],
                    ["文因互联有限公司", "ORG", [12, 20]]
                ]
            }
        }
        mock_request.return_value = mock_response
        
        content = "邓小平同志在北京会见了文因互联有限公司的代表。"
        result = self.ner_tool(content)
        
        assert result["ori_text"] == content
        assert len(result["ner_result"]) == 3
        # 验证人名识别
        assert ["邓小平", "PER", [0, 3]] in result["ner_result"]
        # 验证地名识别
        assert ["北京", "LOC", [6, 8]] in result["ner_result"]
        # 验证机构名识别
        assert ["文因互联有限公司", "ORG", [12, 20]] in result["ner_result"]
    
    @patch('httpx.request')
    def test_call_financial_entities(self, mock_request):
        """测试财务相关实体识别"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "Result": {
                "ori_text": "公司2023年净利润为1000万元，研发费用占营业收入的比重为15.5%。",
                "ner_result": [
                    ["2023年", "DATE", [2, 7]],
                    ["净利润", "NUMERICAL", [7, 10]],
                    ["1000万元", "AMOUNT", [11, 17]],
                    ["研发费用", "INDEPENDENT-ACCO", [18, 22]],
                    ["营业收入", "NUMERICAL", [23, 27]],
                    ["15.5%", "RATIO", [31, 36]]
                ]
            }
        }
        mock_request.return_value = mock_response
        
        content = "公司2023年净利润为1000万元，研发费用占营业收入的比重为15.5%。"
        result = self.ner_tool(content)
        
        assert result["ori_text"] == content
        assert len(result["ner_result"]) == 6
        
        # 验证各种财务实体类型
        entity_types = [item[1] for item in result["ner_result"]]
        assert "DATE" in entity_types
        assert "NUMERICAL" in entity_types
        assert "AMOUNT" in entity_types
        assert "INDEPENDENT-ACCO" in entity_types
        assert "RATIO" in entity_types
    
    @patch('httpx.request')
    def test_invalid_json_response(self, mock_request):
        """测试无效JSON响应"""
        mock_response = Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_request.return_value = mock_response
        
        with pytest.raises(ValueError):
            self.ner_tool("测试文本")
    
    @patch('httpx.request')
    def test_request_ner_private_method(self, mock_request):
        """测试__request_ner私有方法（通过__call__方法间接测试）"""
        mock_response = Mock()
        mock_response.json.return_value = {"Result": {"test": "response"}}
        mock_request.return_value = mock_response
        
        # 调用__call__方法，内部会调用__request_ner
        result = self.ner_tool("测试")
        
        # 验证__request_ner的行为
        mock_request.assert_called_once_with(
            "POST",
            self.test_url,
            headers={'Content-Type': 'application/json'},
            json={'data': "测试"}
        )
        
        assert result == {"test": "response"}
    
    @patch('httpx.request')
    def test_special_characters(self, mock_request):
        """测试特殊字符处理"""
        special_text = "测试@#$%^&*()文本\n\t包含特殊字符"
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "Result": {
                "ori_text": special_text,
                "ner_result": []
            }
        }
        mock_request.return_value = mock_response
        
        result = self.ner_tool(special_text)
        
        assert result["ori_text"] == special_text
        mock_request.assert_called_once_with(
            "POST",
            self.test_url,
            headers={'Content-Type': 'application/json'},
            json={'data': special_text}
        )
    
    @pytest.mark.parametrize("test_input,expected_entities", [
        ("简单文本", []),
        ("", []),
        ("包含数字123的文本", [["123", "QUANTITY", [4, 7]]]),
    ])
    @patch('httpx.request')
    def test_various_inputs(self, mock_request, test_input, expected_entities):
        """测试各种输入参数"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "Result": {
                "ori_text": test_input,
                "ner_result": expected_entities
            }
        }
        mock_request.return_value = mock_response
        
        result = self.ner_tool(test_input)
        
        assert result["ori_text"] == test_input
        assert result["ner_result"] == expected_entities