#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pytest
from unittest.mock import Mock
from code_executor.tools.tool_defines.ner_regex import NerRegexTool


def test_ner_regex_tool_initialization():
    """测试工具初始化"""
    ner_settings = {'is_use': False, 'url': '', 'timeout': 3.5}
    tool = NerRegexTool(ner_settings)

    assert hasattr(tool, 'search')
    assert hasattr(tool, 'finditer')
    assert hasattr(tool, 'ner_api')


def test_text_length_limit():
    """测试文本长度限制"""
    ner_settings = {'is_use': False, 'url': '', 'timeout': 3.5}
    tool = NerRegexTool(ner_settings)

    long_text = "a" * 1001

    with pytest.raises(ValueError, match="输入文本长度不能超过1000字"):
        tool.search("{@<PER>.*@}", long_text)

    with pytest.raises(ValueError, match="输入文本长度不能超过1000字"):
        tool.finditer("{@<ORG>.*@}", long_text)


def test_tool_methods_exist():
    """测试工具方法存在且可调用"""
    ner_settings = {'is_use': False, 'url': '', 'timeout': 3.5}
    tool = NerRegexTool(ner_settings)

    # 确保方法存在且可调用
    assert callable(getattr(tool, 'search', None))
    assert callable(getattr(tool, 'finditer', None))

    # 测试 NER API 对象存在
    assert tool.ner_api is not None


def test_search_with_mock_ner():
    """使用 Mock NER API 测试 search 方法"""
    ner_settings = {'is_use': False, 'url': '', 'timeout': 3.5}
    tool = NerRegexTool(ner_settings)

    # Mock NER API
    mock_ner_api = Mock()
    mock_ner_api.return_value = [
        {'type': 'PER', 'name': '张三', 'start': 0, 'end': 2, 'recognizer': 'MemeParser'},
        {'type': 'LOC', 'name': '北京', 'start': 3, 'end': 5, 'recognizer': 'MemeParser'},
    ]
    tool.ner_api = mock_ner_api

    # 测试匹配
    pattern = "{@<PER>.*@}在{@<LOC>.*@}开会"
    content = "张三在北京开会"

    match = tool.search(pattern, content)

    # 验证 NER API 被调用
    mock_ner_api.assert_called_once_with(content)

    # 验证匹配结果
    assert match is not None
    assert match.group(0) == "张三在北京开会"
    assert match.span() == (0, 7)


def test_finditer_with_mock_ner():
    """使用 Mock NER API 测试 finditer 方法"""
    ner_settings = {'is_use': False, 'url': '', 'timeout': 3.5}
    tool = NerRegexTool(ner_settings)

    # Mock NER API - 返回单个组织（简化测试）
    mock_ner_api = Mock()
    mock_ner_api.return_value = [
        {'type': 'ORG', 'name': '腾讯', 'start': 0, 'end': 2, 'recognizer': 'MemeParser'},
    ]
    tool.ner_api = mock_ner_api

    # 测试查找所有组织
    pattern = "{@<ORG>.*@}"
    content = "腾讯公司很棒"

    matches = tool.finditer(pattern, content)

    # 验证 NER API 被调用
    mock_ner_api.assert_called_once_with(content)

    # 验证找到1个匹配
    assert len(matches) == 1
    assert matches[0].group(0) == "腾讯"


def test_no_match_with_mock_ner():
    """测试无匹配情况"""
    ner_settings = {'is_use': False, 'url': '', 'timeout': 3.5}
    tool = NerRegexTool(ner_settings)

    # Mock NER API - 返回空结果
    mock_ner_api = Mock()
    mock_ner_api.return_value = []
    tool.ner_api = mock_ner_api

    # 测试无匹配
    pattern = "{@<PER>.*@}"
    content = "这里没有人名"

    match = tool.search(pattern, content)
    matches = tool.finditer(pattern, content)

    # 验证结果
    assert match is None
    assert matches == []

    # 验证 NER API 被调用了2次
    assert mock_ner_api.call_count == 2