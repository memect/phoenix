import sys
import json

# 基于输入信息分析文档
input_data = {
    "doc": "fact_extract_llm_smoke",
    "total_pages": 3,
    "chapter_ranges": [{"chapter": "LLM Smoke", "page_start": 1, "page_end": 3}],
    "outline_preview": "",
    "samples": [],
    "required_profile": {
        "domain": "history|science|biography|philosophy|fiction|mixed",
        "focus_axes": ["主题1", "主题2"],
        "classification_notes": "分类规则说明"
    },
    "required_task_fields": ["task_id", "chapter", "pages", "focus"],
    "constraints": [
        "优先按章节切分；章节过长时按8-15页切分。",
        "尽量跳过前言、目录、参考文献等非正文。",
        "focus 要具体说明该任务主要抽取什么事实。"
    ]
}

print("文档信息:")
print(f"文档名: {input_data['doc']}")
print(f"总页数: {input_data['total_pages']}")
print(f"章节数: {len(input_data['chapter_ranges'])}")

for i, chapter in enumerate(input_data['chapter_ranges']):
    print(f"\n章节 {i+1}:")
    print(f"  标题: {chapter['chapter']}")
    print(f"  页码范围: {chapter['page_start']}-{chapter['page_end']}")
    print(f"  页数: {chapter['page_end'] - chapter['page_start'] + 1}")