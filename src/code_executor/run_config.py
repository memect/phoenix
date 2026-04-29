"""
运行配置模块

提供评估配置和执行功能。
"""

import traceback
from typing import Any
from .executor import execute
from pydantic import BaseModel


class EvalResult(BaseModel):
    """评估结果模型"""
    info: str
    extracted_data: Any


async def eval_config(extract_code_config: dict, data: Any) -> EvalResult:
    """评估提取代码配置
    
    Args:
        extract_code_config: 提取代码配置字典
        data: 输入数据（Article 格式）
        
    Returns:
        EvalResult: 包含信息和提取数据的结果
        
    Raises:
        Exception: 配置格式错误时抛出
    """
    article = data
    if '__type__' in extract_code_config:
        try:
            if extract_code_config['__type__'] == 'single':
                return await eval_object(extract_code_config['__data__'], article)
            elif extract_code_config['__type__'] == 'all':
                return await eval_all(extract_code_config['__data__'], article)
            else:
                raise Exception('cant be here')
        except KeyError:
            raise Exception("""代码配置错误,请按如下配置：
旧格式：
{'<field>': '<code>', ...}
新格式：
{'__type__': 'single',
'__data__': {'<field>': '<code>', ...}
}
{'__type__': 'all',
'__data__': '<code>'
}
""")
    return await eval_object(extract_code_config, article)


async def eval_all(code: str, article: Any) -> EvalResult:
    """评估全量代码
    
    Args:
        code: 提取代码字符串
        article: 输入文章数据
        
    Returns:
        EvalResult: 评估结果
    """
    info = ''
    result = None
    try:
        result = await execute(program=code, data=article)
    except Exception:
        info = traceback.format_exc()
    return EvalResult(info=info, extracted_data=result)


async def eval_object(code_json: dict, article: Any) -> EvalResult:
    """评估对象代码
    
    Args:
        code_json: 字段到代码的映射字典
        article: 输入文章数据
        
    Returns:
        EvalResult: 评估结果
    """
    result = {}
    error_info = []
    for attr, code in code_json.items():
        try:
            attr_value = await execute(program=code, data=article)
            if len(attr_value) == 1:
                result[attr] = list(attr_value.values())[0]
            else:
                result[attr] = attr_value
        except Exception as e:
            result[attr] = None
            error_info.append(f"Error evaluating {attr}: {e}")
            continue
    return EvalResult(info="\n".join(error_info), extracted_data=result)
