from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models.chat_models import BaseChatModel
from .models import LLM


def get_llm_client(type: str, base_url: str, api_key: str, model: str) -> BaseChatModel:
    """获取 LangChain LLM 客户端
    
    Args:
        type: LLM 类型，'openai' 或 'google'
        api_key: LLM API 密钥
        model: LLM 模型名称
        
    Returns:
        BaseChatModel: LangChain 聊天模型实例
        
    Raises:
        ValueError: 当 LLM 类型不支持时
    """
    
    if type == 'openai':
        # 直接使用 llm_config_entry.config，相信 Pydantic 的类型检查
        model = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=0.1,  # 默认温度，可以根据需要调整
            max_tokens=8000,  # 设置为模型最大输出长度
        )
        return model
    elif type == 'google':
        model = ChatGoogleGenerativeAI(
            google_api_key=api_key,
            model=model,
            temperature=0.1,  # 默认温度，可以根据需要调整
            max_output_tokens=16384,  # 增加输出长度限制，避免代码被截断
        )
        return model
    else:
        # 这个分支理论上不应该被执行。
        # 如果执行到这里，说明 Settings 加载或 LLM 模型定义可能有问题，
        # 或者 LLM 模型定义已更改但此代码未更新。
        raise ValueError(
            f"不支持的 LLM 类型: '{type}'。"
            f"目前仅支持 'openai' 和 'google' 类型。"
        )


def get_llm_client_by_model(llm_config: LLM) -> BaseChatModel:
    """获取 LangChain LLM 客户端
    
    Args:
        type: LLM 类型，'openai' 或 'google'
        api_key: LLM API 密钥
        model: LLM 模型名称
        
    Returns:
        BaseChatModel: LangChain 聊天模型实例
        
    Raises:
        ValueError: 当 LLM 类型不支持时
    """
    type = llm_config.type
    config = llm_config.config
    api_key = config.api_key
    base_url = config.api_base
    model = config.model
    
    if type == 'openai':
        # 直接使用 llm_config_entry.config，相信 Pydantic 的类型检查
        model = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=0.1,  # 默认温度，可以根据需要调整
            max_tokens=8000,  # 设置为模型最大输出长度
        )
        return model
    elif type == 'google':
        model = ChatGoogleGenerativeAI(
            google_api_key=api_key,
            model=model,
            temperature=0.1,  # 默认温度，可以根据需要调整
            max_output_tokens=16384,  # 增加输出长度限制，避免代码被截断
        )
        return model
    else:
        # 这个分支理论上不应该被执行。
        # 如果执行到这里，说明 Settings 加载或 LLM 模型定义可能有问题，
        # 或者 LLM 模型定义已更改但此代码未更新。
        raise ValueError(
            f"不支持的 LLM 类型: '{type}'。"
            f"目前仅支持 'openai' 和 'google' 类型。"
        )


def get_llm_by_name(llm_configs: dict[str, LLM], name: str) -> BaseChatModel:
    llm_config = llm_configs[name]
    return get_llm_client_by_model(llm_config)