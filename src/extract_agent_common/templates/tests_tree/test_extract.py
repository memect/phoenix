"""提取程序单元测试

测试数据必须硬编码在测试中，不依赖外部数据源。

使用方法：
    pytest tests/ -v
    pytest tests/test_extract.py::test_xxx -v
"""
from program import extract
from code_executor.document.models import (
    Document, 
    HeadingNode, 
    ParagraphNode, 
    TableNode,
    Cell,
)
from code_executor.document.models.base import BBox, TextLine
from code_executor.tools import create_tool_hub


def test_extract_with_mock_document():
    """示例：使用手工构造的 Document 测试 extract 函数"""
    # 1. 创建空文档
    document = Document()
    
    # 2. 构造根节点
    root = HeadingNode(
        id=0,
        type="root",
        page_number=0,
        end_page_number=0,
        parent_path=[],
        text="",
        _doc=document,
    )
    document._root = root
    
    # 3. 添加第一个章节标题
    section1 = HeadingNode(
        id=1,
        type="title",
        page_number=1,
        end_page_number=1,
        parent_path=[0],
        text="第一章 示例章节",
        textlines=[
            TextLine(
                text="第一章 示例章节",
                bold=True,
                bbox=BBox(0, 0, 100, 20),
                page_number=1,
            )
        ],
        _doc=document,
    )
    root._children.append(section1)
    
    # 4. 在第一章下添加段落
    paragraph1 = ParagraphNode(
        id=2,
        type="section",
        page_number=1,
        end_page_number=1,
        parent_path=[0, 1],
        textlines=[
            TextLine(
                text="这是第一章的第一段内容。",
                bold=False,
                bbox=BBox(0, 30, 100, 50),
                page_number=1,
            )
        ],
        _doc=document,
    )
    section1._children.append(paragraph1)
    
    # 5. 添加表格节点
    table = TableNode(
        id=3,
        type="table",
        page_number=1,
        end_page_number=1,
        parent_path=[0, 1],
        row_num=2,
        col_num=2,
        cells=[
            Cell(
                text="Header1",
                bold=True,
                row_index=0,
                col_index=0,
                row_span=1,
                col_span=1,
                bbox=BBox(0, 0, 50, 10),
                page_number=1,
            ),
            Cell(
                text="Header2",
                bold=True,
                row_index=0,
                col_index=1,
                row_span=1,
                col_span=1,
                bbox=BBox(50, 0, 100, 10),
                page_number=1,
            ),
            Cell(
                text="Data1",
                bold=False,
                row_index=1,
                col_index=0,
                row_span=1,
                col_span=1,
                bbox=BBox(0, 10, 50, 20),
                page_number=1,
            ),
            Cell(
                text="Data2",
                bold=False,
                row_index=1,
                col_index=1,
                row_span=1,
                col_span=1,
                bbox=BBox(50, 10, 100, 20),
                page_number=1,
            ),
        ],
        is_merged=False,
        is_merged_part=False,
        _doc=document,
    )
    section1._children.append(table)
    
    # 6. 构建索引（关键步骤！）
    document._build_indices()
    
    # 7. 执行提取
    result = extract(document, create_tool_hub([], {}))
    
    # 8. 验证结果
    assert "sections" in result
    assert len(result["sections"]) == 1
    assert result["sections"][0]["title"] == "第一章 示例章节"
    assert result["sections"][0]["level"] == 1
    
    assert "first_section_title" in result
    assert result["first_section_title"] == "第一章 示例章节"
    
    assert "first_section_paragraphs" in result
    assert len(result["first_section_paragraphs"]) == 1
    assert result["first_section_paragraphs"][0] == "这是第一章的第一段内容。"
    
    assert "tables" in result
    assert len(result["tables"]) == 1
    assert result["tables"][0]["size"] == "2x2"
    assert result["tables"][0]["rows"][0] == ["Header1", "Header2"]
    assert result["tables"][0]["rows"][1] == ["Data1", "Data2"]


# === 回归测试示例 ===
# def test_regression_specific_case():
#     """回归测试：描述具体问题"""
#     document = Document()
#     # ... 构造测试用的 document
#     result = extract(document, create_tool_hub([], {}))
#     assert result.get("field") == "expected_value"
