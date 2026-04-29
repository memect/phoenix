from typing import Literal
from pydantic import BaseModel

class OpenAILLMConfig(BaseModel):
    api_key: str
    api_base: str
    model: str

class LLM(BaseModel):
    type: Literal['openai', 'google'] = 'openai'
    config: OpenAILLMConfig