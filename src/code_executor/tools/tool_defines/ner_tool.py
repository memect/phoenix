"""
实体识别工具
"""

import json

from code_executor.tools.tool_center import tool
from pydantic import BaseModel, Field
from typing import Annotated, Any

import httpx


@tool(name='ner_tool', methods=['__call__'], description='实体识别工具')
class NerTool:
    """实体识别工具"""
    def __init__(self, url: str):
        self.url = url

    def __call__(self, content: Annotated[str, '需要进行实体识别的文本']) -> dict:
        """对输入文本进行命名实体识别(NER)处理。
        
        该方法接收一段文本内容，通过HTTP请求调用远程NER服务，
        识别文本中的命名实体（如人名、地名、机构名等），并返回识别结果。
        
        目前可以识别的实体表格：

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
        
        Args:
            content (str): 需要进行实体识别的文本内容。文本应为字符串格式，
                         可以是单句话、段落或完整文档。
        
        Returns:
            dict: NER服务返回的实体识别结果。返回格式取决于远程服务的实现，
                        通常包含识别出的实体及其类型、位置等信息。
                        
        Raises:
            httpx.RequestError: 当HTTP请求失败时抛出。
            httpx.HTTPStatusError: 当远程服务返回非2xx状态码时抛出。
            
        Example:
            >>> result = ner_tool("腾讯、字节跳动等公司宣布捐款1亿元。")
            >>> print(result)
            {"ori_text": "腾讯、字节跳动等公司宣布捐款1亿元。", "ner_result": [["腾讯", "ORG", [0, 2]], ["字节跳动", "ORG", [3, 7]], ["1亿元", "AMOUNT", [14, 17]]]}
        """
        return self.__request_ner(content)
        
    
    def __request_ner(self, content: str) -> dict:
        """向远程NER服务发送HTTP POST请求进行实体识别。
        
        该方法封装了与远程NER服务的通信逻辑，将文本内容以JSON格式
        发送给指定的服务端点，并返回处理结果。
        
        Args:
            content (str): 需要进行实体识别的文本内容。
            
        Returns:
            dict: 远程NER服务返回的JSON响应数据，包含识别出的实体信息。
            
        Raises:
            httpx.RequestError: 当网络请求失败时抛出。
            httpx.HTTPStatusError: 当远程服务返回错误状态码时抛出。
        """
        payload = {
         "data": content
        }
        headers = {
         'Content-Type': 'application/json'
        }
        response = httpx.request("POST", self.url, headers=headers, json=payload)

        return json.loads(response.json()['Result'])
