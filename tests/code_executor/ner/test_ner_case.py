#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest 测试 NerRegexTool 的用法
验证文档中的示例是否正确工作
"""

import pytest
from code_executor.tools.tool_defines.ner_regex import NerRegexTool


class MockNerApi:
    """模拟 NER API 类"""

    def __call__(self, text):
        """模拟 NER API 调用"""
        if "张三" in text and "北京" in text:
            return [
                {'type': 'PER', 'name': '张三', 'start': 0, 'end': 2, 'recognizer': 'MemeParser'},
                {'type': 'LOC', 'name': '北京', 'start': 3, 'end': 5, 'recognizer': 'MemeParser'},
            ]
        elif "腾讯" in text and "阿里巴巴" in text:
            return [
                {'type': 'ORG', 'name': '腾讯', 'start': 0, 'end': 2, 'recognizer': 'MemeParser'},
                {'type': 'ORG', 'name': '阿里巴巴', 'start': 3, 'end': 7, 'recognizer': 'MemeParser'},
            ]
        elif "1000万元" in text:
            return [
                {'type': 'AMOUNT', 'name': '1000万', 'start': 2, 'end': 7, 'recognizer': 'MemeParser'},
            ]
        elif "报错" in text:
            raise Exception("模拟错误")
        return []


@pytest.fixture
def ner_tool():
    """创建 NerRegexTool 实例的 fixture"""
    ner_settings = {'is_use': False, 'url': '', 'timeout': 3.5}
    tool = NerRegexTool(ner_settings)
    tool.ner_api = MockNerApi()
    return tool


def test_simple_entity_matching(ner_tool):
    """测试文档示例1：简单实体匹配"""
    pattern = "{@<PER>.*@}在{@<LOC>.*@}会见"
    content = "张三在北京会见客户"

    match = ner_tool.search(pattern, content)

    assert match is not None
    assert match.group(0) == "张三在北京会见"
    assert match.span() == (0, 7)


def test_named_group_matching(ner_tool):
    """测试文档示例2：命名组匹配"""
    pattern = "{@<PER>.*@}在{@<LOC>.*@}会见(?P<target>.*)"
    content = "张三在北京会见重要客户"

    match = ner_tool.search(pattern, content)

    assert match is not None
    assert match.group("target") == "重要客户"
    assert match.groupdict() == {"target": "重要客户"}


def test_finditer_multiple_matches(ner_tool):
    """测试 finditer 方法：查找多个匹配"""
    pattern = "{@<ORG>.*@}"
    content = "腾讯和阿里巴巴合作"

    matches = ner_tool.finditer(pattern, content)

    assert len(matches) == 2
    assert matches[0].group(0) == "腾讯"
    assert matches[0].span() == (0, 2)
    assert matches[1].group(0) == "阿里巴巴"
    assert matches[1].span() == (3, 7)


def test_amount_matching(ner_tool):
    """测试金额匹配"""
    pattern = "{@<AMOUNT>.*@}"
    content = "投资1000万元"

    match = ner_tool.search(pattern, content)

    assert match is not None
    assert match.group(0) == "1000万"
    assert match.span() == (2, 7)


def test_no_match(ner_tool):
    """测试无匹配情况"""
    pattern = "{@<PER>.*@}"
    content = "这是一段没有人名的文本"

    match = ner_tool.search(pattern, content)

    assert match is None


def test_text_length_limit(ner_tool):
    """测试文本长度限制"""
    long_text = "a" * 1001

    with pytest.raises(ValueError, match="输入文本长度不能超过1000字"):
        ner_tool.search("{@<PER>.*@}", long_text)


def test_finditer_text_length_limit(ner_tool):
    """测试 finditer 方法的文本长度限制"""
    long_text = "a" * 1001

    with pytest.raises(ValueError, match="输入文本长度不能超过1000字"):
        ner_tool.finditer("{@<PER>.*@}", long_text)


def test_match_object_methods(ner_tool):
    """测试 Match 对象的各种方法"""
    pattern = "(?P<person>{@<PER>.*@})在(?P<location>{@<LOC>.*@})会见"
    content = "张三在北京会见客户"

    match = ner_tool.search(pattern, content)

    assert match is not None
    # 测试 group 方法
    assert match.group(0) == "张三在北京会见"
    assert match.group("person") == "张三"
    assert match.group("location") == "北京"

    # 测试 groupdict 方法
    assert match.groupdict() == {"person": "张三", "location": "北京"}

    # 测试 span 方法
    assert match.span() == (0, 7)

    # 测试 regs 属性
    assert isinstance(match.regs, tuple)
    assert len(match.regs) >= 1