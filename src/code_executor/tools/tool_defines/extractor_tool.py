"""
信息提取工具
"""

import re
from code_executor.tools.tool_center import tool
from pydantic import BaseModel
from typing import Annotated
from langchain_core.language_models import BaseChatModel


def clean_think_tags(text: str) -> str:
    """清洗大模型输出中的 <think>...</think> 标签。
    
    某些模型（如 DeepSeek）会在输出前添加思考过程，需要清理掉。
    """
    # 移除 <think>...</think> 标签及其内容（支持多行）
    return re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL).strip()


@tool(name='extract', methods=['__call__', 'get_max_content_length'], description='信息提取工具')
class ExtractTool:
    """信息提取工具 - 从文本中提取结构化信息
    
    支持多种用法：
    
    用法一：正常提取 - 从文本中提取多个字段
        ```python
        class PersonInfo(BaseModel):
            name: str | None = Field(description="姓名")
            age: int | None = Field(description="年龄")
            
        result = extract_tool(content="张三今年25岁", schema=PersonInfo)
        # {'name': '张三', 'age': 25}
        ```
    
    用法二：分类 - 将文本分类到指定类别
        ```python
        from typing import Literal
        
        class SentimentResult(BaseModel):
            '''对用户评论进行情感分析，判断用户对产品的态度'''
            sentiment: Literal["positive", "negative", "neutral"] = Field(
                description="情感分类: positive-正面评价, negative-负面评价, neutral-中性评价"
            )
            
        result = extract_tool(content="这个产品很好用", schema=SentimentResult)
        # {'sentiment': 'positive'}
        ```
    """
    def __init__(self, llm: BaseChatModel, max_content_length: int = 100000):
        self.llm = llm
        self.max_content_length = max_content_length

    def get_max_content_length(self) -> int:
        """获取最大内容长度限制
        
        Returns:
            int: 最大内容长度
        """
        return self.max_content_length

    def __call__(self, content: str, schema: Annotated[type[BaseModel], '描述提取结构的pydantic BaseModel 子类']) -> dict:
        """从内容中提取结构化信息。
        
        Args:
            content: 要提取信息的文本内容 (长度需要在max_content_length字以内)
            schema: 描述提取结构的pydantic BaseModel 子类, 注意:必须是 pydantic BaseModel 的子类，不能是List[...], dict[...], etc.
            
        Returns:
            提取的结构化数据 (dict)

        Raises:
            ValueError: 如果内容长度超过max_content_length
        """
        if len(content) >= self.max_content_length:
            raise ValueError(f"内容长度不能超过{self.max_content_length}字")

        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import PydanticOutputParser
        from langchain_core.runnables import RunnableLambda
        
        # 使用SchemaConverter创建Pydantic模型
        model = schema
        
        # 创建输出解析器
        output_parser = PydanticOutputParser(pydantic_object=model)
        
        # 创建提示模板
        prompt = ChatPromptTemplate.from_messages([
            ("system", """/no-think 你是一个专业的信息提取专家。请根据给定的JSON schema从文本内容中提取相应的信息。
            
请严格按照schema的结构和字段类型进行提取，确保输出的JSON格式正确。
如果某个字段在文本中找不到对应信息，请设置为null。

{format_instructions}"""),
            ("user", "请从以下内容中提取信息：\n\n{content}")
        ])
        
        # 清洗 LLM 输出中的 <think> 标签
        def clean_llm_output(message):
            message.content = clean_think_tags(message.content)
            return message
        
        # 使用LCEL创建链，添加清洗步骤
        chain = prompt | self.llm | RunnableLambda(clean_llm_output) | output_parser
        
        # 执行提取并返回结果
        result = chain.invoke({
            "content": content,
            "format_instructions": output_parser.get_format_instructions()
        })
        
        # 转换为JSON格式返回
        if hasattr(result, 'model_dump'):
            return result.model_dump()
        elif hasattr(result, 'dict'):
            return result.dict()
        else:
            return result
