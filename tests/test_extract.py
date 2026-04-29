import json
from program import (
    extract,
    extract_basic_info,
    extract_financial_data,
)


def load_document(doc_id: str):
    """加载docjson文档"""
    from code_executor.document.models.document import Document
    
    with open(f".xdev/data/docjson/{doc_id}.json", "r", encoding="utf-8") as f:
        docjson = json.load(f)
    return Document.from_dict(docjson)


def test_extract_basic_info_field_names():
    """测试基本信息字段名提取"""
    # 模拟的标注数据（用于验证提取逻辑）
    expected_fields = {
        "公司中文全称",
        "证券简称",
        "证券代码",
        "法定代表人",
        "行业分类",
        "主要产品与服务项目",
        "普通股总股本",
        "实际控制人",
    }
    
    # 确保 extract_basic_info 返回所有必需字段
    doc = load_document("2821be047fd848d183f3ba76c67f4fb9")
    result = extract_basic_info(doc)
    assert set(result.keys()) == expected_fields


def test_extract_financial_data_field_names():
    """测试财务数据字段名提取"""
    expected_fields = {
        "营业收入_2024",
        "营业收入_2023",
        "毛利率_2024",
        "归属于上市公司股东的净利润_2024",
        "归属于上市公司股东的净利润_2023",
        "基本每股收益_2024",
        "资产总计_2024末",
        "负债总计_2024末",
        "归属于上市公司股东的净资产_2024末",
        "资产负债率_2024末",
    }
    
    doc = load_document("2821be047fd848d183f3ba76c67f4fb9")
    result = extract_financial_data(doc)
    assert set(result.keys()) == expected_fields


def test_田野股份_完整提取():
    """测试文档 2821be047fd848d183f3ba76c67f4fb9（田野股份）的完整提取"""
    doc = load_document("2821be047fd848d183f3ba76c67f4fb9")
    result = extract(doc)
    
    assert result["公司中文全称"] == "田野创新股份有限公司"
    assert result["证券简称"] == "田野股份"
    assert result["证券代码"] == "832023"
    assert result["法定代表人"] == "姚玖志"
    assert result["普通股总股本"] == "327,304,000"
    assert result["营业收入_2024"] == "493,547,697.05"
    assert result["营业收入_2023"] == "459,804,548.04"
    assert result["毛利率_2024"] == "20.52%"
    assert result["归属于上市公司股东的净利润_2024"] == "9,654,654.33"
    assert result["归属于上市公司股东的净利润_2023"] == "33,378,146.86"
    assert result["基本每股收益_2024"] == "0.0295"
    assert result["资产总计_2024末"] == "1,576,471,323.68"
    assert result["资产负债率_2024末"] == "24.20%"


def test_广道数字_负值处理():
    """测试文档 2529252caee449e48d1eb74a2bd82022（广道数字）的负值提取"""
    doc = load_document("2529252caee449e48d1eb74a2bd82022")
    result = extract(doc)
    
    # 验证负值保留负号
    assert result["归属于上市公司股东的净利润_2024"] == "-30,761,481.03"
    assert result["归属于上市公司股东的净利润_2023"] == "-31,253,998.29"
    assert result["基本每股收益_2024"] == "-0.60"


def test_泰鹏智能_实际控制人_多人():
    """测试文档 54d784951d07421a9a908dd7967e16aa（泰鹏智能）的实际控制人字段"""
    doc = load_document("54d784951d07421a9a908dd7967e16aa")
    result = extract(doc)
    
    # 验证实际控制人完整提取（包含多人信息）
    assert "刘建三、石峰、范明、李雪梅、王绪华、王健、孙远奇、韩帮银" in result["实际控制人"]
    assert "一致行动人" in result["实际控制人"]


def test_数值格式保持():
    """测试数值格式保持（千分位、百分号）"""
    doc = load_document("2821be047fd848d183f3ba76c67f4fb9")
    result = extract(doc)
    
    # 千分位逗号
    assert "," in result["营业收入_2024"]
    assert "," in result["普通股总股本"]
    
    # 百分号
    assert "%" in result["毛利率_2024"]
    assert "%" in result["资产负债率_2024末"]
    
    # 小数点
    assert "." in result["营业收入_2024"]
    assert "." in result["基本每股收益_2024"]
