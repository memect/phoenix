"""
VLM 图片信息提取工具
"""

import re
import base64
from pathlib import Path
from typing import Annotated
from pydantic import BaseModel
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from code_executor.tools.tool_center import tool


def clean_think_tags(text: str) -> str:
    """清洗大模型输出中的 <think>...</think> 标签。"""
    return re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL).strip()


def guess_mime_type(data: bytes) -> str:
    """根据 magic number 推断图片 MIME 类型。
    
    Args:
        data: 图片二进制数据
        
    Returns:
        MIME 类型字符串
    """
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if data[:2] == b'\xff\xd8':
        return 'image/jpeg'
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    if data[:4] == b'RIFF' and len(data) > 12 and data[8:12] == b'WEBP':
        return 'image/webp'
    if data[:4] == b'<svg' or b'<svg' in data[:100]:
        return 'image/svg+xml'
    # fallback
    return 'image/png'


def to_data_url(data: bytes) -> str:
    """将二进制数据转换为 data URL。
    
    Args:
        data: 图片二进制数据
        
    Returns:
        data:image/xxx;base64,... 格式的字符串
    """
    mime_type = guess_mime_type(data)
    b64 = base64.b64encode(data).decode('utf-8')
    return f"data:{mime_type};base64,{b64}"


ImageInput = str | bytes


@tool(name='vlm_extract', methods=['__call__'], description='VLM图片信息提取工具')
class VLMExtractTool:
    """VLM 图片信息提取工具 - 从图片中提取结构化信息
    
    支持多种图片输入格式：
    - URL: http:// 或 https:// 开头的图片链接
    - base64: data:image/... 开头的 base64 编码字符串
    - 本地文件路径: 自动读取并转换为 base64
    - bytes: 二进制数据，自动转换为 base64
    
    示例：
        ```python
        from pydantic import BaseModel, Field
        
        class DocumentInfo(BaseModel):
            title: str | None = Field(description="文档标题")
            date: str | None = Field(description="日期")
            
        # 单张图片
        result = vlm_extract_tool("/path/to/image.png", schema=DocumentInfo)
        
        # 多张图片（如多页文档）
        result = vlm_extract_tool(["/page1.png", "/page2.png"], schema=DocumentInfo)
        ```
    """
    
    def __init__(
        self, 
        llm: BaseChatModel, 
        max_image_size: int = 20 * 1024 * 1024,
    ):
        """初始化 VLM 提取工具。
        
        Args:
            llm: 支持视觉的语言模型（如 gpt-4o, gemini-2.5-flash 等）
            max_image_size: 单张图片最大大小（字节），默认 20MB
        """
        self.llm = llm
        self.max_image_size = max_image_size

    def _normalize_image(self, image: ImageInput) -> dict:
        """将图片输入转换为 OpenAI 格式的 image_url 对象。
        
        Args:
            image: 图片输入（URL/base64/路径/bytes）
            
        Returns:
            {"type": "image_url", "image_url": {"url": "..."}}
            
        Raises:
            ValueError: 图片大小超过限制
            FileNotFoundError: 本地文件不存在
        """
        # bytes 类型：转 base64
        if isinstance(image, bytes):
            if len(image) > self.max_image_size:
                raise ValueError(f"图片大小 {len(image)} 字节超过限制 {self.max_image_size} 字节")
            url = to_data_url(image)
            return {"type": "image_url", "image_url": {"url": url}}
        
        # 字符串类型
        if isinstance(image, str):
            # URL
            if image.startswith('http://') or image.startswith('https://'):
                return {"type": "image_url", "image_url": {"url": image}}
            
            # 已经是 base64
            if image.startswith('data:image/'):
                return {"type": "image_url", "image_url": {"url": image}}
            
            # 本地文件路径
            path = Path(image)
            if not path.exists():
                raise FileNotFoundError(f"图片文件不存在: {image}")
            
            data = path.read_bytes()
            if len(data) > self.max_image_size:
                raise ValueError(f"图片文件 {image} 大小 {len(data)} 字节超过限制 {self.max_image_size} 字节")
            
            url = to_data_url(data)
            return {"type": "image_url", "image_url": {"url": url}}
        
        raise TypeError(f"不支持的图片类型: {type(image)}")

    def __call__(
        self, 
        images: Annotated[ImageInput | list[ImageInput], '图片输入，支持 URL/base64/本地路径/bytes，可以是单张或列表'],
        schema: Annotated[type[BaseModel], '描述提取结构的 pydantic BaseModel 子类'],
    ) -> dict:
        """从图片中提取结构化信息。
        
        Args:
            images: 图片输入，支持：
                - URL (http/https 开头)
                - base64 字符串 (data:image/... 开头)
                - 本地文件路径
                - bytes 二进制数据
                - 以上类型的列表（多图场景）
            schema: 描述提取结构的 pydantic BaseModel 子类
            
        Returns:
            提取的结构化数据 (dict)
            
        Raises:
            ValueError: 图片大小超过限制
            FileNotFoundError: 本地文件不存在
        """
        from langchain_core.output_parsers import PydanticOutputParser
        from langchain_core.runnables import RunnableLambda
        
        # 统一转成列表
        if not isinstance(images, list):
            images = [images]
        
        if not images:
            raise ValueError("至少需要提供一张图片")
        
        # 转换所有图片
        image_contents = [self._normalize_image(img) for img in images]
        
        # 创建输出解析器
        output_parser = PydanticOutputParser(pydantic_object=schema)
        
        # 构建 prompt
        system_prompt = """/no-think 你是一个专业的图片信息提取专家。请根据给定的 JSON schema 从图片中提取相应的信息。

请严格按照 schema 的结构和字段类型进行提取，确保输出的 JSON 格式正确。
如果某个字段在图片中找不到对应信息，请设置为 null。

{format_instructions}"""
        
        user_prompt = "请从以下图片中提取信息："
        
        # 构建消息内容
        content = [
            {"type": "text", "text": user_prompt},
            *image_contents,
        ]
        
        # 构建完整消息
        messages = [
            {"role": "system", "content": system_prompt.format(
                format_instructions=output_parser.get_format_instructions()
            )},
            {"role": "user", "content": content},
        ]
        
        # 调用 LLM
        response = self.llm.invoke(messages)
        
        # 清洗输出
        cleaned_content = clean_think_tags(response.content)
        
        # 解析结果
        result = output_parser.parse(cleaned_content)
        
        # 转换为 dict
        if hasattr(result, 'model_dump'):
            return result.model_dump()
        elif hasattr(result, 'dict'):
            return result.dict()
        else:
            return result
