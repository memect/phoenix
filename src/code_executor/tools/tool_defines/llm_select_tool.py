"""
大模型段落筛选工具
"""

import re
import json
from typing import Annotated
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from code_executor.tools.tool_center import tool
from code_executor.structure import Table


def clean_think_tags(text: str) -> str:
    """清洗大模型输出中的 <think>...</think> 标签。"""
    return re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL).strip()


def table_to_text(table: Table) -> str:
    """将表格转为文本格式"""
    try:
        table_data = table.table_data
        rows, cols = table.row_num, table.col_num
        lines = []
        for row_idx in range(rows):
            row_cells = []
            for col_idx in range(cols):
                cell = str(table_data[row_idx, col_idx])
                row_cells.append(cell)
            lines.append(" | ".join(row_cells))
        return "\n".join(lines)
    except Exception as e:
        return f"[表格解析失败: {e}]"


def format_paragraphs_with_index(paragraphs: list[str | Table]) -> tuple[str, dict[int, str | Table]]:
    """
    将段落列表编号，返回格式化文本和索引映射
    
    Returns:
        formatted_text: 带编号的段落文本
        index_map: 编号到原始段落的映射
    """
    formatted_lines = []
    index_map = {}
    
    for idx, item in enumerate(paragraphs):
        if isinstance(item, Table):
            table_text = table_to_text(item)
            formatted_lines.append(f"[{idx}] [表格]\n{table_text}")
            index_map[idx] = item
        else:
            text = item.strip()
            if text:
                formatted_lines.append(f"[{idx}] {text}")
                index_map[idx] = text
    
    return "\n\n".join(formatted_lines), index_map


@tool(name='llm_select', methods=['__call__', 'get_max_content_length'], description='大模型段落筛选工具')
class LLMSelectTool:
    """大模型段落筛选工具 - 使用LLM从文本段落中筛选包含目标信息的段落"""
    
    def __init__(self, llm: BaseChatModel, max_content_length: int = 100000):
        self.llm = llm
        self.max_content_length = max_content_length

    def get_max_content_length(self) -> int:
        """获取最大内容长度限制
        
        Returns:
            int: 最大内容长度
        """
        return self.max_content_length

    def __call__(
        self, 
        paragraphs: Annotated[list[str | Table], '段落列表，可包含文本或表格'],
        target: Annotated[str, '要查找的目标信息'],
    ) -> list[int]:
        """从段落列表中筛选包含目标信息的段落编号。
        
        Args:
            paragraphs: 段落列表，可包含文本字符串或Table对象
            target: 要查找的目标信息，如"资助金额"、"合同签订日期"
            
        Returns:
            list[int]: 包含目标信息的段落索引列表，索引对应 paragraphs 的下标
            
        Raises:
            ValueError: 如果段落总长度超过 max_content_length
        """
        return self.select_paragraphs(paragraphs, target)

    def select_paragraphs(
        self, 
        paragraphs: Annotated[list[str | Table], '段落列表，可包含文本或表格'],
        target: Annotated[str, '要查找的目标信息'],
    ) -> list[int]:
        """从段落列表中筛选包含目标信息的段落编号。
        
        Args:
            paragraphs: 段落列表，可包含文本字符串或Table对象
            target: 要查找的目标信息，如"资助金额"、"合同签订日期"
            
        Returns:
            list[int]: 包含目标信息的段落索引列表，索引对应 paragraphs 的下标
            
        Raises:
            ValueError: 如果段落总长度超过 max_content_length
        """
        if not paragraphs:
            return []
        
        # 格式化段落，添加编号
        formatted_text, index_map = format_paragraphs_with_index(paragraphs)
        
        if not index_map:
            return []
        
        # 检查长度限制
        if len(formatted_text) > self.max_content_length:
            raise ValueError(f"段落总长度 {len(formatted_text)} 超过限制 {self.max_content_length}")
        
        # 构建 prompt
        prompt = f"""/nothink
找出包含"{target}"的段落编号。
只输出编号数组，如[1,3]或[]

{formatted_text}"""

        # 调用 LLM
        response = self.llm.invoke([HumanMessage(content=prompt)])
        content = clean_think_tags(response.content).strip()
        
        # 解析返回的编号数组
        try:
            match = re.search(r'\[[\d,\s]*\]', content)
            if match:
                indices = [int(i) for i in json.loads(match.group())]
                # 过滤有效的索引
                return [idx for idx in indices if idx in index_map]
        except (json.JSONDecodeError, ValueError):
            pass
        
        return []
