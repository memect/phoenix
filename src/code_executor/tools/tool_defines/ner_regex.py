"""
NER 正则工具
"""

from code_executor.tools.tool_center import tool
from typing import Annotated

from code_executor.ner import NERPattern, Match
from code_executor.ner.get_ner_results import NerApi


@tool(name='ner_regex_tool', methods=['search', 'finditer'])
class NerRegexTool:
    """嵌入命名实体识别符号的正则工具

    结合NER和正则表达式，基于实体类型进行文本模式匹配。

    语法说明：
    使用 {@<实体类型>.*@} 匹配该类型实体，可组合多个实体和普通文本。

    Match对象重要属性：
    - groupdict(): 返回命名组匹配结果字典
    - group(index/name): 返回指定分组内容，支持数字索引和组名
    - span(): 匹配在原文的位置范围
    - regs: 所有分组的位置信息元组列表

    支持的实体类型：

    | 英文名称 | 实体名称 | 释义 | 备注 |
    | --- | --- | --- | --- |
    | PER | 人名 | 人的名字，如"邓小平"等。 |  |
    | LOC | 地名 | 如"中国"、"北京"等。 |  |
    | ORG | 组织机构名 | 如"文因互联有限公司"。 |  |
    | TITLE | 职务名 | 职务所具有的头衔称谓。如会计师、会计机构负责人、第三届董事、法定代表人、教授、高级工程师、院士等。 |  |
    | NUMERICAL | 指标名 | 主要是指经济领域中一些和金额、数值、百分比等相关的指标名称。如未分配利润、净利润、所得税、注册资本等。 |  |
    | AMOUNT | 金额 | 如"公司的研发费用分别为6,586.39万元、9,592.94万元和15,195.19万元"中的金额。 |  |
    | RATIO | 占比 | 如"占营业收入的比重分别为20.80%、22.29%和23.73%"中的百分比数。 |  |
    | QUANTITY | 数量 | 如"桌子上共有35个苹果"中的"35个"。 |  |
    | DATE | 日期 | 如"从2019年7月8日至今"中的"2019年7月8日"。 |  |
    | TIME | 时间 | 如"现在是北京时间19:23:12"中的"19:23:12"。 |  |
    | CONFERENCE | 会议名称 | 如"贵州茅台发布第三届董事会2021年度第七次会议决议公告显示"中的"第三届董事会2021年度第七次会议"。 |  |
    | TEL | 电话 | 包括手机号、座机号等。 |  |
    | EMAIL | 邮箱 | 即邮箱地址。 |  |
    | ADDRESS | 地址 | 如"我的地址：北京市海淀区三虎桥小区9号楼"中的"地址：北京市海淀区三虎桥小区9号楼"。 |  |
    | STKCD | 证券代码 | 如"证券简称：st天宝，证券代码：002220，公告编号2019-067"中的"002220"。 |  |
    | STKSN | 证券简称 | 如"证券简称：st天宝，证券代码：002220，公告编号2019-067"中的"st天宝"。 |  |
    | INDEPENDENT-ACCO | 财务科目 | INDEPENDENT是通用的指标名称，INDEPENDENT-ACCO是指标名的一个子类，表示和财务紧密相关的指标名称，如"存货周转率"、"管理费用"、"研发费用"等。 |  |

    示例：
    ```python
    # 简单实体匹配
    pattern = "{@<PER>.*@}在{@<LOC>.*@}会见"
    match = tool.search(pattern, "张三在北京会见客户")
    if match:
        print(match.group(0))          # 张三在北京会见
        print(match.span())            # (0, 7)

    # 在普通文本部分使用命名组提取信息
    pattern = "{@<PER>.*@}在{@<LOC>.*@}会见(?P<target>.*)"
    match = tool.search(pattern, "张三在北京会见重要客户")
    if match:
        print(match.group("target"))   # 重要客户
        print(match.groupdict())       # {'target': '重要客户'}
    ```
    
    **如何写pattern**
    你可以使用NER正则模式，将实体类型用{@<实体类型>.*@}括起来，如"{@<ORG>.*@}在{@<LOC>.*@}成立"。
    在普通文本部分使用命名组提取信息，如"{@<ORG>.*@}在{@<LOC>.*@}成立(?P<target>.*)"。
    **注意：**
    你应该尽量结合正则和NER，避免过于宽泛的模式，如"{@<ORG>.*@}"这样的模式，这过于宽泛了。
    """
    def __init__(self, ner_settings: dict):
        """
        Args:
            ner_settings: NER服务配置，包含：
                - is_use: 是否使用NER服务
                - url: NER服务地址
                - timeout: 超时时间
        """
        self.ner_api = NerApi(ner_settings)


    def search(self, pattern: str, content: Annotated[str, '需要进行实体识别的文本']) -> Match|None:
        """查找第一个匹配的模式

        Args:
            pattern: NER正则模式，如 "{@<ORG>.*@}宣布"
            content: 要搜索的文本，不能超过1000字

        Returns:
            Match对象（如果找到匹配）或None。Match对象可用:
            - groupdict(): 获取命名组字典
            - group(index/name): 获取分组内容
            - span(): 获取匹配位置范围

        Raises:
            ValueError: 当输入文本长度超过1000字时

        Example:
            match = tool.search("{@<AMOUNT>.*@}", "投资1000万元")
            if match:
                print(f"找到金额，位置：{match.span()}")
        """
        MAX_LEN = 1000
        if len(content) > MAX_LEN:
            raise ValueError(f'输入文本长度不能超过{MAX_LEN}字')

        ner_pattern = NERPattern(pattern, 0, self.ner_api)
        return ner_pattern.search(content)
        
        
    def finditer(self, pattern: str, content: Annotated[str, '需要进行实体识别的文本']) -> list[Match]:
        """查找所有匹配的模式

        Args:
            pattern: NER正则模式
            content: 要搜索的文本，不能超过1000字

        Returns:
            Match对象列表，每个Match可用groupdict()和group()提取信息

        Raises:
            ValueError: 当输入文本长度超过1000字时

        Example:
            matches = tool.finditer("{@<ORG>.*@}", "腾讯和阿里巴巴合作")
            print(f"找到{len(matches)}个机构")
        """
        MAX_LEN = 1000
        if len(content) > MAX_LEN:
            raise ValueError(f'输入文本长度不能超过{MAX_LEN}字')

        ner_pattern = NERPattern(pattern, 0, self.ner_api)
        matches = ner_pattern.finditer(content)
        # 过滤掉None值，确保返回的都是Match对象
        return [match for match in matches if match is not None]
