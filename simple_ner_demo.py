#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NER工具系统核心原理演示
简化版本，专注于展示核心概念
"""

def demo_ner_workflow():
    """演示NER工具系统的核心工作流程"""
    
    print("=== NER工具系统核心工作流程演示 ===\n")
    
    # 1. 原始输入
    text = "腾讯、字节跳动等公司宣布捐款1亿元，张三表示很高兴"
    ner_pattern = '{@<ORG>.*@}等公司宣布捐款{@<AMOUNT>.*@}'
    
    print(f"1. 输入文本: '{text}'")
    print(f"2. NER正则模式: '{ner_pattern}'")
    print()
    
    # 2. 模拟NER识别结果
    ner_results = [
        {'type': 'ORG', 'name': '腾讯', 'start': 0, 'end': 2},
        {'type': 'ORG', 'name': '字节跳动', 'start': 3, 'end': 7},
        {'type': 'AMOUNT', 'name': '1亿元', 'start': 14, 'end': 17},
        {'type': 'PER', 'name': '张三', 'start': 19, 'end': 21},
    ]
    
    print("3. NER识别结果:")
    for result in ner_results:
        print(f"   - '{result['name']}' ({result['type']}) 位置[{result['start']}:{result['end']}]")
    print()
    
    # 3. 标记替换过程
    print("4. 标记替换过程:")
    print(f"   原始文本: '{text}'")
    
    # 模拟标记替换（实际实现更复杂）
    # 使用特殊字符标记不同类型的实体
    START_TAGS = {'ORG': '◤', 'AMOUNT': '◣', 'PER': '◐'}
    END_TAGS = {'ORG': '◥', 'AMOUNT': '◢', 'PER': '◑'}
    
    # 按位置倒序插入标记（避免位置偏移）
    tagged_text = text
    for result in sorted(ner_results, key=lambda x: x['start'], reverse=True):
        start, end = result['start'], result['end']
        entity_type = result['type']
        if entity_type in START_TAGS:
            start_tag = START_TAGS[entity_type]
            end_tag = END_TAGS[entity_type]
            tagged_text = tagged_text[:start] + start_tag + tagged_text[start:end] + end_tag + tagged_text[end:]
    
    print(f"   标记后文本: '{tagged_text}'")
    print(f"   说明: ◤◥=ORG, ◣◢=AMOUNT, ◐◑=PER")
    print()
    
    # 4. 正则模式转换
    print("5. 正则模式转换:")
    print(f"   原始模式: '{ner_pattern}'")
    
    # 将NER模式转换为实际正则表达式
    converted_pattern = ner_pattern.replace('{@<ORG>.*@}', '◤.*?◥').replace('{@<AMOUNT>.*@}', '◣.*?◢')
    print(f"   转换后模式: '{converted_pattern}'")
    print()
    
    # 5. 正则匹配
    import re
    print("6. 正则匹配:")
    match = re.search(converted_pattern, tagged_text)
    if match:
        print(f"   匹配成功!")
        print(f"   匹配内容: '{match.group()}'")
        print(f"   匹配位置: {match.span()}")
        
        # 6. 位置映射回原文
        print()
        print("7. 位置映射回原文:")
        print("   (简化演示，实际实现需要复杂的位置映射算法)")
        print(f"   原文匹配内容: '腾讯、字节跳动等公司宣布捐款1亿元'")
        print(f"   对应原文位置: [0:17]")
    else:
        print("   未找到匹配")
    
    print()

def demo_tag_string_concept():
    """演示TagString的核心概念"""
    
    print("=== TagString核心概念演示 ===\n")
    
    text = "北京大学的张教授"
    entities = [
        {'type': 'ORG', 'start': 0, 'end': 4, 'name': '北京大学'},
        {'type': 'PER', 'start': 5, 'end': 8, 'name': '张教授'}
    ]
    
    print(f"原始文本: '{text}'")
    print("实体信息:")
    for e in entities:
        print(f"  - '{e['name']}' ({e['type']}) [{e['start']}:{e['end']}]")
    print()
    
    # 演示标记点的概念
    print("标记点概念:")
    print("  位置0: ORG开始")
    print("  位置4: ORG结束") 
    print("  位置5: PER开始")
    print("  位置8: PER结束")
    print()
    
    # 演示插入标记后的效果
    print("插入标记后:")
    print("  原文: '北京大学的张教授'")
    print("  标记: '◤北京大学◥的◐张教授◑'")
    print("  说明: 通过标记可以在正则中精确定位实体")
    print()

def demo_string_with_ner():
    """演示StringWithNER的使用"""
    
    print("=== StringWithNER使用演示 ===\n")
    
    # 模拟StringWithNER的核心功能
    class SimpleStringWithNER:
        def __init__(self, content, entities):
            self.content = content
            self.entities = entities
        
        def get_entities(self):
            return self.entities
        
        def get_entity_types(self):
            return set(e['type'] for e in self.entities)
    
    # 创建带NER信息的字符串
    text = "邓小平在北京会见了腾讯公司的代表"
    entities = [
        {'type': 'PER', 'name': '邓小平', 'start': 0, 'end': 3},
        {'type': 'LOC', 'name': '北京', 'start': 4, 'end': 6}, 
        {'type': 'ORG', 'name': '腾讯公司', 'start': 10, 'end': 14}
    ]
    
    ner_string = SimpleStringWithNER(text, entities)
    
    print(f"文本内容: '{ner_string.content}'")
    print("实体列表:")
    for entity in ner_string.get_entities():
        print(f"  - {entity['name']} ({entity['type']}) [{entity['start']}:{entity['end']}]")
    
    print(f"实体类型: {ner_string.get_entity_types()}")
    print()

if __name__ == "__main__":
    demo_ner_workflow()
    demo_tag_string_concept() 
    demo_string_with_ner()