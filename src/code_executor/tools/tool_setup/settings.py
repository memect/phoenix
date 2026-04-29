"""
工具设置配置模块 - 纯数据模型
"""

from pydantic import BaseModel
from langchain_llm.models import LLM

DEFAULT_EXTRACT_MAX_CONTENT_LENGTH = 50000
DEFAULT_LLM_SELECT_MAX_CONTENT_LENGTH = DEFAULT_EXTRACT_MAX_CONTENT_LENGTH


class NerRegexToolConfig(BaseModel):
    is_use: bool = True
    url: str = "http://localhost:6225/nlp_tools/ner"
    timeout: float = 3.5


class ExtractToolConfig(BaseModel):
    llm: LLM
    max_content_length: int = DEFAULT_EXTRACT_MAX_CONTENT_LENGTH


class LLMSelectToolConfig(BaseModel):
    llm: LLM
    max_content_length: int = DEFAULT_LLM_SELECT_MAX_CONTENT_LENGTH


class VLMExtractToolConfig(BaseModel):
    llm: LLM
    max_image_size: int = 20 * 1024 * 1024


class PDFToImageToolConfig(BaseModel):
    dpi: int = 150


class ToolsSetup(BaseModel):
    ner_regex_tool: NerRegexToolConfig | None = None
    extract_tool: ExtractToolConfig | None = None
    llm_select_tool: LLMSelectToolConfig | None = None
    vlm_extract_tool: VLMExtractToolConfig | None = None
    pdf_to_image_tool: PDFToImageToolConfig | None = None
