"""
工具加载模块
"""

from code_executor.tools.tool_center import set_global_policy, Policy
from .settings import ToolsSetup
from langchain_llm import get_llm_client_by_model


def build_code_tools_policy(
    setting: ToolsSetup,
    enabled_tools: list[str] | None = None,
) -> Policy:
    """根据配置构造代码工具策略。
    
    Args:
        setting: 工具配置
        enabled_tools: 启用的工具名称列表，None 表示启用所有配置的工具
                      可选值: 'ner_regex_tool', 'extract'
    """
    tool_names = []
    tool_config = {}
    
    if setting.ner_regex_tool is not None:
        if enabled_tools is None or 'ner_regex_tool' in enabled_tools:
            tool_names.append('ner_regex_tool')
            tool_config['ner_regex_tool'] = {
                'args': [{
                    'is_use': setting.ner_regex_tool.is_use,
                    'url': setting.ner_regex_tool.url,
                    'timeout': setting.ner_regex_tool.timeout
                }]
            }
    
    if setting.extract_tool is not None:
        if enabled_tools is None or 'extract' in enabled_tools:
            tool_names.append('extract')
            llm = get_llm_client_by_model(setting.extract_tool.llm)
            tool_config['extract'] = {
                'args': [llm],
                'kwargs': {
                    'max_content_length': setting.extract_tool.max_content_length
                }
            }
    
    if setting.llm_select_tool is not None:
        if enabled_tools is None or 'llm_select' in enabled_tools:
            tool_names.append('llm_select')
            llm = get_llm_client_by_model(setting.llm_select_tool.llm)
            tool_config['llm_select'] = {
                'args': [llm],
                'kwargs': {
                    'max_content_length': setting.llm_select_tool.max_content_length
                }
            }
    
    if setting.vlm_extract_tool is not None:
        if enabled_tools is None or 'vlm_extract' in enabled_tools:
            tool_names.append('vlm_extract')
            llm = get_llm_client_by_model(setting.vlm_extract_tool.llm)
            tool_config['vlm_extract'] = {
                'args': [llm],
                'kwargs': {
                    'max_image_size': setting.vlm_extract_tool.max_image_size
                }
            }
    
    if setting.pdf_to_image_tool is not None:
        if enabled_tools is None or 'pdf_to_image' in enabled_tools:
            tool_names.append('pdf_to_image')
            tool_config['pdf_to_image'] = {
                'kwargs': {
                    'dpi': setting.pdf_to_image_tool.dpi
                }
            }
    
    return Policy(tool_names=tool_names, tool_config=tool_config)


def setup_code_tools(setting: ToolsSetup, enabled_tools: list[str] | None = None) -> Policy:
    """设置代码工具，并返回生成的策略。"""
    policy = build_code_tools_policy(setting, enabled_tools)
    set_global_policy(policy)
    return policy
