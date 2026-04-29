from code_executor.document.models.document import Document
from code_executor.document.models.nodes import HeadingNode, TableNode
from typing import Any


def extract(document: Document) -> dict[str, Any]:
    """从北交所年报中提取基本信息和财务数据"""
    result = {}

    # 提取基本信息（第二节 公司概况）
    result.update(extract_basic_info(document))

    # 提取财务数据（第三节 会计数据和财务指标）
    result.update(extract_financial_data(document))

    return result


def extract_basic_info(document: Document) -> dict[str, str | None]:
    """提取第二节公司概况的基本信息"""
    result = {
        "公司中文全称": None,
        "证券简称": None,
        "证券代码": None,
        "法定代表人": None,
        "行业分类": None,
        "主要产品与服务项目": None,
        "普通股总股本": None,
        "实际控制人": None,
    }

    # 定位第二节
    for node in document.iter_nodes("title"):
        title_text = node.get_text().strip()
        if "第二节" in title_text and "公司概况" in title_text:
            # 在第二节下查找子表格
            for child in node.get_children():
                if isinstance(child, HeadingNode):
                    child_text = child.get_text().strip()

                    # 一、基本信息
                    if "一、基本信息" in child_text or "基本信息" == child_text:
                        table = find_next_table(child)
                        if table:
                            extract_basic_info_table(table, result)

                    # 四、企业信息
                    elif "四、企业信息" in child_text or "企业信息" == child_text:
                        table = find_next_table(child)
                        if table:
                            extract_enterprise_info_table(table, result)
            break

    return result


def extract_basic_info_table(table: TableNode, result: dict):
    """从基本信息表格提取字段"""
    for i in range(table.row_num):
        row_data = table.row(i)
        if len(row_data) < 2:
            continue

        field_name = row_data[0].strip()
        field_value = row_data[1].strip()

        if "公司中文全称" in field_name:
            result["公司中文全称"] = field_value
        elif "证券简称" in field_name:
            result["证券简称"] = field_value
        elif "证券代码" in field_name:
            result["证券代码"] = field_value
        elif "法定代表人" in field_name:
            result["法定代表人"] = field_value


def extract_enterprise_info_table(table: TableNode, result: dict):
    """从企业信息表格提取字段"""
    for i in range(table.row_num):
        row_data = table.row(i)
        if len(row_data) < 2:
            continue

        field_name = row_data[0].strip()
        field_value = row_data[1].strip()

        if "行业分类" in field_name:
            result["行业分类"] = field_value
        elif "主要产品与服务项目" in field_name:
            result["主要产品与服务项目"] = field_value
        elif "普通股总股本" in field_name:
            result["普通股总股本"] = field_value
        elif "实际控制人" in field_name:
            result["实际控制人"] = field_value


def extract_financial_data(document: Document) -> dict[str, str | None]:
    """提取第三节会计数据和财务指标"""
    result = {
        "营业收入_2024": None,
        "营业收入_2023": None,
        "毛利率_2024": None,
        "归属于上市公司股东的净利润_2024": None,
        "归属于上市公司股东的净利润_2023": None,
        "基本每股收益_2024": None,
        "资产总计_2024末": None,
        "负债总计_2024末": None,
        "归属于上市公司股东的净资产_2024末": None,
        "资产负债率_2024末": None,
    }

    # 定位第三节
    for node in document.iter_nodes("title"):
        title_text = node.get_text().strip()
        if "第三节" in title_text and (
            "会计数据" in title_text or "财务指标" in title_text
        ):
            for child in node.get_children():
                if isinstance(child, HeadingNode):
                    child_text = child.get_text().strip()

                    # 一、盈利能力
                    if "一、盈利能力" in child_text or "盈利能力" == child_text:
                        table = find_next_table(child)
                        if table:
                            extract_profitability_table(table, result)

                    # 二、营运情况
                    elif "二、营运情况" in child_text or "营运情况" == child_text:
                        table = find_next_table(child)
                        if table:
                            extract_operation_table(table, result)
            break

    return result


def extract_profitability_table(table: TableNode, result: dict):
    """从盈利能力表格提取字段"""
    # 解析表头（第一行）
    header = table.row(0)
    col_2024 = None
    col_2023 = None

    for i, h in enumerate(header):
        h_text = h.strip()
        if "2024年" in h_text or "2024" == h_text:
            col_2024 = i
        elif "2023年" in h_text or "2023" == h_text:
            col_2023 = i

    # 遍历数据行
    for i in range(1, table.row_num):
        row_data = table.row(i)
        if len(row_data) == 0:
            continue

        row_name = row_data[0].strip()

        # 营业收入（精确匹配）
        if row_name == "营业收入":
            if col_2024 is not None and col_2024 < len(row_data):
                result["营业收入_2024"] = row_data[col_2024].strip()
            if col_2023 is not None and col_2023 < len(row_data):
                result["营业收入_2023"] = row_data[col_2023].strip()

        # 毛利率
        elif row_name.startswith("毛利率"):
            if col_2024 is not None and col_2024 < len(row_data):
                result["毛利率_2024"] = row_data[col_2024].strip()

        # 归属于上市公司股东的净利润（精确匹配，排除扣除非经常性损益的）
        elif row_name == "归属于上市公司股东的净利润":
            if col_2024 is not None and col_2024 < len(row_data):
                result["归属于上市公司股东的净利润_2024"] = row_data[col_2024].strip()
            if col_2023 is not None and col_2023 < len(row_data):
                result["归属于上市公司股东的净利润_2023"] = row_data[col_2023].strip()

        # 基本每股收益
        elif row_name == "基本每股收益" or row_name.startswith("基本每股收益"):
            if col_2024 is not None and col_2024 < len(row_data):
                result["基本每股收益_2024"] = row_data[col_2024].strip()


def extract_operation_table(table: TableNode, result: dict):
    """从营运情况表格提取字段"""
    # 解析表头（找到"2024年末"列）
    header = table.row(0)
    col_2024_end = None

    for i, h in enumerate(header):
        h_text = h.strip()
        if "2024年末" in h_text or "2024末" in h_text:
            col_2024_end = i
            break

    # 遍历数据行
    for i in range(1, table.row_num):
        row_data = table.row(i)
        if len(row_data) == 0:
            continue

        row_name = row_data[0].strip()

        # 资产总计
        if row_name == "资产总计":
            if col_2024_end is not None and col_2024_end < len(row_data):
                result["资产总计_2024末"] = row_data[col_2024_end].strip()

        # 负债总计
        elif row_name == "负债总计":
            if col_2024_end is not None and col_2024_end < len(row_data):
                result["负债总计_2024末"] = row_data[col_2024_end].strip()

        # 归属于上市公司股东的净资产（精确匹配，排除每股净资产）
        elif row_name == "归属于上市公司股东的净资产":
            if col_2024_end is not None and col_2024_end < len(row_data):
                result["归属于上市公司股东的净资产_2024末"] = row_data[
                    col_2024_end
                ].strip()

        # 资产负债率（合并）
        elif "资产负债率" in row_name and "合并" in row_name:
            if col_2024_end is not None and col_2024_end < len(row_data):
                result["资产负债率_2024末"] = row_data[col_2024_end].strip()


def find_next_table(node: HeadingNode) -> TableNode | None:
    """查找节点下的第一个表格"""
    for child in node.get_children():
        if isinstance(child, TableNode):
            return child
    return None
