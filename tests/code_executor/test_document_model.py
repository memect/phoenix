"""Document 模型单元测试

使用真实 doc.json 测试 Document、Node、TableNode 的新增方法。
数据源：resources/SINGLE_FILES/91cb4734-8acd-f4cc-7db0-3a27c00bfb51/doc.json
"""

import json
from pathlib import Path

import pytest

from code_executor.document.models.document import Document
from code_executor.document.models.nodes import (
    HeadingNode,
    ParagraphNode,
    TableNode,
)

DOC_JSON_PATH = (
    Path(__file__).resolve().parents[2]
    / "resources"
    / "SINGLE_FILES"
    / "91cb4734-8acd-f4cc-7db0-3a27c00bfb51"
    / "doc.json"
)


@pytest.fixture(scope="module")
def doc() -> Document:
    """加载真实 doc.json 构建 Document"""
    with open(DOC_JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return Document.from_dict(data)


# ===== Document 级别测试 =====


class TestDocumentBasic:
    """Document 基础功能"""

    def test_from_dict_has_root(self, doc: Document):
        assert doc._root is not None

    def test_from_dict_has_nodes(self, doc: Document):
        assert len(doc._id_to_node) > 0

    def test_total_pages(self, doc: Document):
        assert doc.total_pages > 0

    def test_pdf_info(self, doc: Document):
        assert "producer" in doc.pdf_info


class TestDocumentGetAllTexts:
    """Document.get_all_texts()"""

    def test_returns_nonempty(self, doc: Document):
        texts = doc.get_all_texts()
        assert len(texts) > 0

    def test_all_items_are_str(self, doc: Document):
        texts = doc.get_all_texts(max_items=20)
        assert all(isinstance(t, str) for t in texts)

    def test_no_empty_strings(self, doc: Document):
        texts = doc.get_all_texts(max_items=50)
        assert all(len(t) > 0 for t in texts)

    def test_max_items_limit(self, doc: Document):
        texts = doc.get_all_texts(max_items=5)
        assert len(texts) == 5

    def test_max_items_none_returns_all(self, doc: Document):
        texts = doc.get_all_texts()
        # 文档有 554 title + 1223 section，非空文本应该很多
        assert len(texts) > 100


class TestDocumentIterNodes:
    """Document.iter_nodes()"""

    def test_iter_all(self, doc: Document):
        all_nodes = list(doc.iter_nodes())
        assert len(all_nodes) > 0

    def test_filter_table(self, doc: Document):
        tables = list(doc.iter_nodes("table"))
        assert len(tables) > 0
        assert all(isinstance(n, TableNode) for n in tables)

    def test_filter_title(self, doc: Document):
        titles = list(doc.iter_nodes("title"))
        assert len(titles) > 0
        assert all(isinstance(n, HeadingNode) for n in titles)

    def test_filter_section(self, doc: Document):
        sections = list(doc.iter_nodes("section"))
        assert len(sections) > 0
        assert all(isinstance(n, ParagraphNode) for n in sections)


class TestDocumentGetNode:
    """Document.get_node()"""

    def test_existing_node(self, doc: Document):
        node = doc.get_node(55)
        assert node is not None
        assert isinstance(node, TableNode)

    def test_nonexistent_node(self, doc: Document):
        assert doc.get_node(999999) is None

    def test_root_first_child(self, doc: Document):
        node = doc.get_node(1)
        assert node is not None
        assert isinstance(node, HeadingNode)
        assert "易点天下" in node.get_text()


# ===== Node 导航测试 =====


class TestNodeNavigation:
    """Node 导航方法"""

    def test_get_children(self, doc: Document):
        # id=60: "四、其他有关资料"，有 section + table 混合子节点
        node = doc.get_node(60)
        assert node is not None
        children = node.get_children()
        assert len(children) > 0

    def test_get_parent(self, doc: Document):
        # id=60 的子节点应该能回溯到 id=60
        node = doc.get_node(60)
        assert node is not None
        children = node.get_children()
        if children:
            child = children[0]
            parent = child.get_parent()
            assert parent is not None
            assert parent.id == node.id

    def test_get_ancestors(self, doc: Document):
        # 找一个有 parent_path 的深层节点
        node = doc.get_node(60)
        assert node is not None
        children = node.get_children()
        if children:
            ancestors = children[0].get_ancestors()
            # 至少应该有一个祖先
            assert len(ancestors) >= 1

    def test_get_siblings(self, doc: Document):
        node = doc.get_node(60)
        assert node is not None
        siblings = node.get_siblings()
        assert len(siblings) >= 1
        # 自己应该在兄弟列表中
        assert any(s.id == node.id for s in siblings)

    def test_level(self, doc: Document):
        node = doc.get_node(60)
        assert node is not None
        assert node.level >= 1


class TestNodeCollectContent:
    """Node.collect_content()"""

    def test_returns_mixed_content(self, doc: Document):
        # id=60: "四、其他有关资料" 有 section + table 子节点
        node = doc.get_node(60)
        assert node is not None
        content = node.collect_content()
        assert len(content) > 0

        # 应该同时包含 str 和 TableNode
        has_str = any(isinstance(c, str) for c in content)
        has_table = any(isinstance(c, TableNode) for c in content)
        assert has_str, "collect_content 应包含文本"
        assert has_table, "collect_content 应包含 TableNode"

    def test_leaf_node_empty(self, doc: Document):
        # section 叶子节点没有子节点，collect_content 应返回空
        for node in doc.iter_nodes("section"):
            if not node.get_children():
                content = node.collect_content()
                assert content == []
                break


# ===== TableNode 方法测试 =====


class TestTableNodeMergedCells:
    """TableNode 方法 - 使用有合并单元格的表格 (id=55, 13×4)"""

    @pytest.fixture()
    def table(self, doc: Document) -> TableNode:
        node = doc.get_node(55)
        assert isinstance(node, TableNode)
        return node

    def test_dimensions(self, table: TableNode):
        assert table.row_num == 13
        assert table.col_num == 4

    def test_cell_at_basic(self, table: TableNode):
        cell = table.cell_at(0, 0)
        assert cell is not None
        assert cell.text == "股票简称"

    def test_cell_at_value(self, table: TableNode):
        cell = table.cell_at(0, 3)
        assert cell is not None
        assert cell.text == "301171"

    def test_cell_at_merged_span(self, table: TableNode):
        # (1,1) 的 col_span=3，覆盖 (1,1), (1,2), (1,3)
        cell_11 = table.cell_at(1, 1)
        assert cell_11 is not None
        assert cell_11.col_span == 3
        assert cell_11.text == "易点天下网络科技股份有限公司"
        # 合并区域内其他位置指向同一个 Cell
        cell_12 = table.cell_at(1, 2)
        assert cell_12 is cell_11
        cell_13 = table.cell_at(1, 3)
        assert cell_13 is cell_11

    def test_cell_at_out_of_range(self, table: TableNode):
        assert table.cell_at(99, 99) is None

    def test_row(self, table: TableNode):
        row0 = table.row(0)
        assert len(row0) == 4
        assert row0 == ["股票简称", "易点天下", "股票代码", "301171"]

    def test_col(self, table: TableNode):
        col0 = table.col(0)
        assert len(col0) == 13
        assert col0[0] == "股票简称"
        assert col0[1] == "公司的中文名称"

    def test_to_text_all(self, table: TableNode):
        text = table.to_text()
        assert "股票简称" in text
        lines = text.strip().split("\n")
        assert len(lines) == 13

    def test_to_text_max_rows(self, table: TableNode):
        text = table.to_text(max_rows=3)
        assert "..." in text
        assert "仅显示前 3 行" in text


class TestTableNodeSimple:
    """TableNode 方法 - 使用简单表格 (id=57, 6×3, 无合并)"""

    @pytest.fixture()
    def table(self, doc: Document) -> TableNode:
        node = doc.get_node(57)
        assert isinstance(node, TableNode)
        return node

    def test_dimensions(self, table: TableNode):
        assert table.row_num == 6
        assert table.col_num == 3

    def test_row(self, table: TableNode):
        row1 = table.row(1)
        assert row1 == ["姓名", "王萍", "梁丹宁"]

    def test_iter_rows_all(self, table: TableNode):
        rows = list(table.iter_rows())
        assert len(rows) == 6

    def test_iter_rows_skip_header(self, table: TableNode):
        rows = list(table.iter_rows(start=1))
        assert len(rows) == 5
        assert rows[0] == ["姓名", "王萍", "梁丹宁"]

    def test_iter_rows_range(self, table: TableNode):
        rows = list(table.iter_rows(start=1, end=3))
        assert len(rows) == 2

    def test_col(self, table: TableNode):
        col1 = table.col(1)
        assert len(col1) == 6
        assert col1[0] == "董事会秘书"
        assert col1[1] == "王萍"

    def test_to_text(self, table: TableNode):
        text = table.to_text()
        assert " | " in text
        assert "董事会秘书" in text

    def test_get_text(self, table: TableNode):
        # get_text 返回所有单元格文本拼接
        text = table.get_text()
        assert "董事会秘书" in text
        assert "王萍" in text
