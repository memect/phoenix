#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NER工具系统使用示例
展示整个NER正则匹配系统的工作流程
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from extract_agent.core.utils.ner import NERPattern, StringWithNER, NerApi
import re

def mock_ner_api(content):
    """模拟NER API，返回预定义的实体识别结果"""
    if "腾讯" in content and "字节跳动" in content:
        return [
            {'type': 'ORG', 'name': '腾讯', 'start': 0, 'end': 2, 'recognizer': 'MemeParser'},
            {'type': 'ORG', 'name': '字节跳动', 'start': 3, 'end': 7, 'recognizer': 'MemeParser'},
            {'type': 'AMOUNT', 'name': '1亿元', 'start': 14, 'end': 17, 'recognizer': 'MemeParser'},
            {'type': 'PER', 'name': '张三', 'start': 19, 'end': 21, 'recognizer': 'MemeParser'},
        ]
    elif "北京" in content:
        return [
            {'type': 'PER', 'name': '邓小平', 'start': 0, 'end': 3, 'recognizer': 'MemeParser'},
            {'type': 'LOC', 'name': '北京', 'start': 6, 'end': 8, 'recognizer': 'MemeParser'},
            {'type': 'ORG', 'name': '文因互联有限公司', 'start': 12, 'end': 20, 'recognizer': 'MemeParser'},
        ]
    return []

def example_1_basic_ner_pattern():
    """示例1: 基础NER正则匹配"""
    print("=== 示例1: 基础NER正则匹配 ===")
    
    # 创建NER API实例
    ner_api = mock_ner_api
    
    # 创建NER正则模式 - 匹配"公司+金额+人名"的模式
    pattern = '{@<ORG>.*@}等公司宣布捐款{@<AMOUNT>.*@}，{@<PER>.*@}表示'
    ner_pattern = NERPattern(pattern, 0, ner_api)
    
    # 测试文本
    text = "腾讯、字节跳动等公司宣布捐款1亿元，张三表示很高兴"
    
    print(f"原始文本: {text}")
    print(f"NER正则模式: {pattern}")
    
    # 执行匹配
    match = ner_pattern.search(text)
    
    if match:
        print(f"匹配成功!")
        print(f"匹配范围: {match.span()}")
        print(f"匹配内容: {match.string[match.span()[0]:match.span()[1]]}")
        print(f"分组结果: {match.groupdict()}")
    else:
        print("未找到匹配")
    
    print()

def example_2_string_with_ner():
    """示例2: 使用StringWithNER"""
    print("=== 示例2: StringWithNER的使用 ===")
    
    # 创建带NER信息的字符串
    text = "邓小平同志在北京会见了文因互联有限公司的代表"
    
    # 手动定义实体（通常这些是由NER API返回的）
    entities = [
        StringWithNER.new_entity(text, 0, 3, 'PER', 'manual'),
        StringWithNER.new_entity(text, 6, 8, 'LOC', 'manual'),
        StringWithNER.new_entity(text, 12, 20, 'ORG', 'manual'),
    ]
    
    ner_string = StringWithNER(text, entities)
    
    print(f"原始文本: {ner_string.content}")
    print(f"实体列表:")
    for entity in ner_string.get_entities():
        print(f"  - {entity['name']} ({entity['type']}) [{entity['start']}:{entity['end']}]")
    
    print()

def example_3_complex_pattern_matching():
    """示例3: 复杂的NER正则匹配"""
    print("=== 示例3: 复杂模式匹配 ===")
    
    ner_api = mock_ner_api
    
    # 更复杂的正则模式 - 匹配人名在地点会见机构的模式
    pattern = '{@<PER>.*@}.*在{@<LOC>.*@}会见.*{@<ORG>.*@}'
    ner_pattern = NERPattern(pattern, 0, ner_api)
    
    text = "邓小平同志在北京会见了文因互联有限公司的代表"
    
    print(f"原始文本: {text}")
    print(f"NER正则模式: {pattern}")
    
    # 获取NER结果
    ner_results = ner_api(text)
    print(f"NER识别结果:")
    for result in ner_results:
        print(f"  - {result['name']} ({result['type']}) [{result['start']}:{result['end']}]")
    
    # 执行匹配
    match = ner_pattern.search(text)
    
    if match:
        print(f"匹配成功!")
        print(f"匹配范围: {match.span()}")
        print(f"匹配文本: '{text[match.span()[0]:match.span()[1]]}'")
    else:
        print("未找到匹配")
    
    print()

def example_4_finditer():
    """示例4: 查找所有匹配"""
    print("=== 示例4: 查找所有匹配 ===")
    
    ner_api = mock_ner_api
    
    # 创建一个匹配组织名的模式
    pattern = '{@<ORG>.*@}'
    ner_pattern = NERPattern(pattern, 0, ner_api)
    
    text = "腾讯、字节跳动等公司宣布捐款1亿元，张三表示很高兴"
    
    print(f"原始文本: {text}")
    print(f"查找所有组织名:")
    
    # 查找所有匹配
    matches = ner_pattern.finditer(text)
    
    for i, match in enumerate(matches, 1):
        if match:
            start, end = match.span()
            matched_text = text[start:end]
            print(f"  匹配{i}: '{matched_text}' 位置[{start}:{end}]")
        else:
            print(f"  匹配{i}: 无有效匹配")
    
    print()

def example_5_tag_string_process():
    """示例5: TagString处理过程展示"""
    print("=== 示例5: TagString处理过程 ===")
    
    # 模拟TagString的工作过程
    text = "腾讯公司和字节跳动公司"
    
    # 模拟NER结果
    ner_results = [
        {'type': 'ORG', 'name': '腾讯公司', 'start': 0, 'end': 4, 'recognizer': 'MemeParser'},
        {'type': 'ORG', 'name': '字节跳动公司', 'start': 5, 'end': 11, 'recognizer': 'MemeParser'},
    ]
    
    print(f"原始文本: '{text}'")
    print(f"NER结果: {ner_results}")
    
    # 手动展示TagString的转换过程
    # 假设使用标记 ◤ 和 ◥
    tagged_text = "◤腾讯公司◥和◤字节跳动公司◥"
    print(f"标记后文本: '{tagged_text}'")
    print(f"说明: ◤ 表示ORG实体开始，◥ 表示ORG实体结束")
    
    print()

def show_system_workflow():
    """展示整个系统的工作流程"""
    print("=== NER正则系统工作流程 ===")
    print("""
1. 文本输入: "腾讯、字节跳动等公司宣布捐款1亿元"

2. NER识别阶段:
   - 调用NER API识别实体
   - 返回: [('腾讯', 'ORG', [0,2]), ('字节跳动', 'ORG', [3,7]), ('1亿元', 'AMOUNT', [14,17])]

3. 标记替换阶段:
   - 原文: "腾讯、字节跳动等公司宣布捐款1亿元"
   - 标记: "◤腾讯◥、◤字节跳动◥等公司宣布捐款◣1亿元◢"
   - 其中: ◤◥表示ORG标记, ◣◢表示AMOUNT标记

4. 正则匹配阶段:
   - 模式: '{@<ORG>.*@}等公司宣布捐款{@<AMOUNT>.*@}'
   - 转换为: '◤.*◥等公司宣布捐款◣.*◢'
   - 在标记文本上执行正则匹配

5. 结果映射阶段:
   - 将标记文本中的匹配位置映射回原始文本位置
   - 返回Match对象，包含原始文本的位置信息
    """)

if __name__ == "__main__":
    show_system_workflow()
    example_1_basic_ner_pattern()
    example_2_string_with_ner()
    example_3_complex_pattern_matching()
    example_4_finditer()
    example_5_tag_string_process()