"""
evaluator.api.evaluate 接口测试

覆盖 Object 和 ListOfObjects 两种数据类型的各种场景。
"""

import pytest
from evaluator.api import evaluate


# ============================================================
# Object 类型
# ============================================================

class TestEvaluateObject:
    """Object 类型：每条记录是一个 dict，逐字段比较"""

    SCHEMA = {"name": "str", "age": "int", "city": "str"}

    def test_all_correct(self):
        """全部字段都正确"""
        result = evaluate(
            extracted_list=[
                {"name": "张三", "age": 30, "city": "北京"},
                {"name": "李四", "age": 25, "city": "上海"},
            ],
            standard_list=[
                {"name": "张三", "age": 30, "city": "北京"},
                {"name": "李四", "age": 25, "city": "上海"},
            ],
            schema=self.SCHEMA,
        )
        assert result.overall_accuracy == 1.0
        assert result.total_correct == 2
        assert result.total_records == 2

    def test_all_incorrect(self):
        """全部字段都错"""
        result = evaluate(
            extracted_list=[
                {"name": "X", "age": 0, "city": "Y"},
                {"name": "A", "age": 0, "city": "B"},
            ],
            standard_list=[
                {"name": "张三", "age": 30, "city": "北京"},
                {"name": "李四", "age": 25, "city": "上海"},
            ],
            schema=self.SCHEMA,
        )
        assert result.overall_accuracy == 0.0
        assert result.total_correct == 0

    def test_partial_correct(self):
        """部分记录正确"""
        result = evaluate(
            extracted_list=[
                {"name": "张三", "age": 30, "city": "北京"},   # 全对
                {"name": "李四", "age": 99, "city": "上海"},   # age 错
                {"name": "王五", "age": 40, "city": "广州"},   # 全对
            ],
            standard_list=[
                {"name": "张三", "age": 30, "city": "北京"},
                {"name": "李四", "age": 25, "city": "上海"},
                {"name": "王五", "age": 40, "city": "广州"},
            ],
            schema=self.SCHEMA,
        )
        assert result.overall_accuracy == pytest.approx(2 / 3)
        assert result.total_correct == 2
        assert result.total_records == 3

    def test_missing_field(self):
        """提取结果缺少字段 → 该记录算 INCORRECT"""
        result = evaluate(
            extracted_list=[
                {"name": "张三"},  # 缺 age 和 city
            ],
            standard_list=[
                {"name": "张三", "age": 30, "city": "北京"},
            ],
            schema=self.SCHEMA,
        )
        assert result.overall_accuracy == 0.0
        # 字段级：name 正确，age/city 缺失
        assert result.field_stats["name"].correct == 1
        assert result.field_stats["age"].missing == 1
        assert result.field_stats["city"].missing == 1

    def test_extra_field_ignored(self):
        """提取结果有多余字段 → 忽略，只看 schema 定义的字段"""
        result = evaluate(
            extracted_list=[
                {"name": "张三", "age": 30, "city": "北京", "phone": "123"},
            ],
            standard_list=[
                {"name": "张三", "age": 30, "city": "北京"},
            ],
            schema=self.SCHEMA,
        )
        assert result.overall_accuracy == 1.0

    def test_field_stats(self):
        """字段级统计"""
        result = evaluate(
            extracted_list=[
                {"name": "张三", "age": 30, "city": "北京"},   # 全对
                {"name": "李四", "age": 99, "city": "深圳"},   # age 错, city 错
            ],
            standard_list=[
                {"name": "张三", "age": 30, "city": "北京"},
                {"name": "李四", "age": 25, "city": "上海"},
            ],
            schema=self.SCHEMA,
        )
        assert result.field_stats["name"].correct == 2
        assert result.field_stats["name"].incorrect == 0
        assert result.field_stats["age"].correct == 1
        assert result.field_stats["age"].incorrect == 1
        assert result.field_stats["city"].correct == 1
        assert result.field_stats["city"].incorrect == 1

    def test_detail_inspection(self):
        """检查每条记录的详情"""
        result = evaluate(
            extracted_list=[
                {"name": "张三", "age": 30},
                {"name": "错误", "age": 25},
            ],
            standard_list=[
                {"name": "张三", "age": 30},
                {"name": "李四", "age": 25},
            ],
            schema={"name": "str", "age": "int"},
            ids=["doc_001", "doc_002"],
        )
        # doc_001 正确
        assert result.details[0].standared_info.id == "doc_001"
        assert result.details[0].type.value == "correct"
        # doc_002 错误
        assert result.details[1].standared_info.id == "doc_002"
        assert result.details[1].type.value == "incorrect"
        # 检查错误字段
        incorrect_details = result.get_incorrect_details()
        assert len(incorrect_details) == 1
        assert incorrect_details[0].standared_info.id == "doc_002"

    def test_single_record(self):
        """单条记录评估"""
        result = evaluate(
            extracted_list=[{"name": "张三"}],
            standard_list=[{"name": "张三"}],
            schema={"name": "str"},
        )
        assert result.overall_accuracy == 1.0
        assert result.total_records == 1

    def test_custom_ids(self):
        """自定义 ID"""
        result = evaluate(
            extracted_list=[{"name": "张三"}, {"name": "李四"}],
            standard_list=[{"name": "张三"}, {"name": "李四"}],
            schema={"name": "str"},
            ids=["invoice_001", "invoice_002"],
        )
        assert result.details[0].standared_info.id == "invoice_001"
        assert result.details[1].standared_info.id == "invoice_002"


# ============================================================
# ListOfObjects 类型
# ============================================================

class TestEvaluateListOfObjects:
    """ListOfObjects 类型：每条记录是一个 list[dict]，Hungarian 匹配后逐字段比较"""

    SCHEMA = {"品名": "str", "数量": "int", "单价": "int"}

    def test_all_correct(self):
        """所有记录的所有对象都匹配正确"""
        result = evaluate(
            extracted_list=[
                [{"品名": "鼠标", "数量": 5, "单价": 50},
                 {"品名": "键盘", "数量": 3, "单价": 200}],
                [{"品名": "显示器", "数量": 1, "单价": 3000}],
            ],
            standard_list=[
                [{"品名": "鼠标", "数量": 5, "单价": 50},
                 {"品名": "键盘", "数量": 3, "单价": 200}],
                [{"品名": "显示器", "数量": 1, "单价": 3000}],
            ],
            schema=self.SCHEMA,
        )
        assert result.overall_accuracy == 1.0
        assert result.total_correct == 2
        assert result.total_records == 2

    def test_missing_object(self):
        """提取结果比标准少了对象 → INCORRECT"""
        result = evaluate(
            extracted_list=[
                [{"品名": "鼠标", "数量": 5, "单价": 50}],
                # 标准有 3 个对象，提取只有 1 个 → 缺失 2 个
            ],
            standard_list=[
                [{"品名": "鼠标", "数量": 5, "单价": 50},
                 {"品名": "键盘", "数量": 3, "单价": 200},
                 {"品名": "耳机", "数量": 2, "单价": 100}],
            ],
            schema=self.SCHEMA,
        )
        assert result.overall_accuracy == 0.0
        detail = result.details[0]
        assert len(detail.matched) == 1
        assert len(detail.missing) == 2  # 键盘 + 耳机

    def test_extra_object(self):
        """提取结果比标准多了对象 → INCORRECT"""
        result = evaluate(
            extracted_list=[
                [{"品名": "鼠标", "数量": 5, "单价": 50},
                 {"品名": "键盘", "数量": 3, "单价": 200},
                 {"品名": "不存在", "数量": 1, "单价": 1}],  # 多余
            ],
            standard_list=[
                [{"品名": "鼠标", "数量": 5, "单价": 50},
                 {"品名": "键盘", "数量": 3, "单价": 200}],
            ],
            schema=self.SCHEMA,
        )
        assert result.overall_accuracy == 0.0
        detail = result.details[0]
        assert len(detail.matched) == 2
        assert len(detail.extra) == 1   # 不存在

    def test_partial_field_mismatch(self):
        """对象匹配上了但部分字段不对 → INCORRECT"""
        result = evaluate(
            extracted_list=[
                [{"品名": "鼠标", "数量": 99, "单价": 50}],  # 数量错
            ],
            standard_list=[
                [{"品名": "鼠标", "数量": 5, "单价": 50}],
            ],
            schema=self.SCHEMA,
        )
        assert result.overall_accuracy == 0.0
        detail = result.details[0]
        assert len(detail.matched) == 1
        m = detail.matched[0]
        assert m.similarity_score < 1.0
        assert "数量" in m.incorrect_fields

    def test_order_independent(self):
        """提取顺序和标准顺序不同，Hungarian 算法能正确匹配"""
        result = evaluate(
            extracted_list=[
                # 顺序反过来
                [{"品名": "键盘", "数量": 3, "单价": 200},
                 {"品名": "鼠标", "数量": 5, "单价": 50}],
            ],
            standard_list=[
                [{"品名": "鼠标", "数量": 5, "单价": 50},
                 {"品名": "键盘", "数量": 3, "单价": 200}],
            ],
            schema=self.SCHEMA,
        )
        assert result.overall_accuracy == 1.0

    def test_multiple_records_mixed(self):
        """多条记录，有对有错"""
        result = evaluate(
            extracted_list=[
                [{"品名": "鼠标", "数量": 5, "单价": 50}],     # 全对
                [{"品名": "显示器", "数量": 1, "单价": 3000},
                 {"品名": "多余", "数量": 1, "单价": 1}],       # 多了一个 → 错
                [{"品名": "笔记本", "数量": 2, "单价": 5000}],  # 全对
            ],
            standard_list=[
                [{"品名": "鼠标", "数量": 5, "单价": 50}],
                [{"品名": "显示器", "数量": 1, "单价": 3000}],
                [{"品名": "笔记本", "数量": 2, "单价": 5000}],
            ],
            schema=self.SCHEMA,
            ids=["inv_001", "inv_002", "inv_003"],
        )
        assert result.overall_accuracy == pytest.approx(2 / 3)
        assert result.total_correct == 2
        assert result.total_records == 3

    def test_empty_list_vs_nonempty(self):
        """提取为空列表，标准有内容 → INCORRECT"""
        result = evaluate(
            extracted_list=[[]],
            standard_list=[
                [{"品名": "鼠标", "数量": 5, "单价": 50}],
            ],
            schema=self.SCHEMA,
        )
        assert result.overall_accuracy == 0.0
        detail = result.details[0]
        assert len(detail.missing) == 1
        assert len(detail.matched) == 0

    def test_both_empty_lists(self):
        """双方都是空列表 → CORRECT"""
        result = evaluate(
            extracted_list=[[]],
            standard_list=[[]],
            schema=self.SCHEMA,
        )
        assert result.overall_accuracy == 1.0

    def test_matched_detail_fields(self):
        """检查 MatchedObjectDetail 的字段"""
        result = evaluate(
            extracted_list=[
                [{"品名": "鼠标", "数量": 5, "单价": 99}],  # 单价错
            ],
            standard_list=[
                [{"品名": "鼠标", "数量": 5, "单价": 50}],
            ],
            schema=self.SCHEMA,
        )
        m = result.details[0].matched[0]
        assert "品名" in m.correct_fields
        assert "数量" in m.correct_fields
        assert "单价" in m.incorrect_fields


# ============================================================
# 错误处理 & 自动检测
# ============================================================

class TestEvaluateEdgeCases:

    def test_auto_detect_object(self):
        """传 dict → 自动识别为 object"""
        result = evaluate(
            extracted_list=[{"name": "张三"}],
            standard_list=[{"name": "张三"}],
            schema={"name": "str"},
        )
        assert result.overall_accuracy == 1.0

    def test_auto_detect_list_of_objects(self):
        """传 list[dict] → 自动识别为 list_of_objects"""
        result = evaluate(
            extracted_list=[[{"name": "张三"}]],
            standard_list=[[{"name": "张三"}]],
            schema={"name": "str"},
        )
        assert result.overall_accuracy == 1.0

    def test_force_eval_type(self):
        """强制指定 eval_type"""
        result = evaluate(
            extracted_list=[{"name": "张三"}],
            standard_list=[{"name": "张三"}],
            schema={"name": "str"},
            eval_type="object",
        )
        assert result.overall_accuracy == 1.0

    def test_length_mismatch_raises(self):
        """extracted 和 standard 数量不一致 → ValueError"""
        with pytest.raises(ValueError, match="不匹配"):
            evaluate(
                extracted_list=[{"name": "张三"}],
                standard_list=[{"name": "张三"}, {"name": "李四"}],
                schema={"name": "str"},
            )

    def test_empty_list_raises(self):
        """空列表 → ValueError"""
        with pytest.raises(ValueError, match="不能为空"):
            evaluate(
                extracted_list=[],
                standard_list=[],
                schema={"name": "str"},
            )

    def test_ids_length_mismatch_raises(self):
        """ids 数量和记录数量不一致 → ValueError"""
        with pytest.raises(ValueError, match="ID 数量"):
            evaluate(
                extracted_list=[{"name": "张三"}],
                standard_list=[{"name": "张三"}],
                schema={"name": "str"},
                ids=["a", "b"],
            )

    def test_generate_report(self):
        """生成文本报告不报错"""
        result = evaluate(
            extracted_list=[{"name": "张三"}, {"name": "错误"}],
            standard_list=[{"name": "张三"}, {"name": "李四"}],
            schema={"name": "str"},
        )
        report = result.generate_report()
        assert isinstance(report, str)
        assert len(report) > 0
