import re
import string
from typing import Any
from difflib import SequenceMatcher
from .core.schema import FieldType

# 文本相似度配置
TEXT_SIMILARITY_LENGTH_THRESHOLD = 50  # 使用相似度比较的最小文本长度
TEXT_SIMILARITY_THRESHOLD = 0.7  # 相似度阈值，默认70%以上认为匹配
TEXT_OVERLAP_LENGTH_THRESHOLD = 4  # 使用公共子串比较的最小文本长度
TEXT_OVERLAP_RATIO_THRESHOLD = 0.6  # 公共子串占标准文本的比例阈值，默认60%以上认为匹配
TEXT_OVERLAP_LENGTH_RATIO_THRESHOLD = 3.0  # 公共子串占标准文本的比例阈值，默认60%以上认为匹配


def _is_amount_or_number_format(text: str) -> bool:
    """
    检查文本是否为金额或数字格式
    
    支持的格式：
    - 纯数字：123, 123.45
    - 带千分位：1,234.56, 1，234.56
    - 带金额符号：¥100, $100, €100
    - 带中文单位：100元, 100万, 100亿
    - 组合形式：¥1,234.56元
    
    Args:
        text: 待检查的文本
        
    Returns:
        如果是金额/数字格式返回True，否则返回False
    """
    if not text:
        return False
    
    # 移除空格
    text = text.strip()
    
    # 检查是否包含金额符号或单位
    amount_symbols = ['¥', '$', '€', '元', '万', '亿']
    has_amount_indicator = any(symbol in text for symbol in amount_symbols)
    
    # 移除所有金额符号、分隔符和单位
    cleaned = text.replace(',', '').replace('，', '').replace(' ', '')
    cleaned = cleaned.replace('¥', '').replace('$', '').replace('€', '')
    cleaned = cleaned.replace('元', '').replace('万', '').replace('亿', '')
    
    # 检查剩余部分是否为纯数字
    try:
        float(cleaned)
        # 如果包含金额指示符或者完全由数字组成，则认为是金额/数字格式
        return has_amount_indicator or cleaned == text
    except ValueError:
        return False


def _extract_numeric_value(text: str) -> str | None:
    """
    从金额/数字格式的文本中提取规范化的数字值
    
    Args:
        text: 金额/数字格式的文本
        
    Returns:
        规范化的数字字符串，如果无法提取则返回None
    """
    if not _is_amount_or_number_format(text):
        return None
    
    # 移除所有金额符号、分隔符和单位
    cleaned = text.replace(',', '').replace('，', '').replace(' ', '')
    cleaned = cleaned.replace('¥', '').replace('$', '').replace('€', '')
    cleaned = cleaned.replace('元', '').replace('万', '').replace('亿', '')
    
    try:
        # 返回规范化的数字字符串
        return str(float(cleaned))
    except ValueError:
        return None


def _calculate_text_similarity(text1: str, text2: str) -> float:
    """
    计算两个文本的相似度（0-1之间）
    
    使用 SequenceMatcher 基于 Ratcliff/Obershelp 算法
    
    Args:
        text1: 第一个文本
        text2: 第二个文本
        
    Returns:
        相似度分数，0表示完全不同，1表示完全相同
    """
    return SequenceMatcher(None, text1, text2).ratio()


def _get_longest_common_substring_length(text1: str, text2: str) -> int:
    """
    获取两个文本的最长公共子串长度
    
    Args:
        text1: 第一个文本
        text2: 第二个文本
        
    Returns:
        最长公共子串的字符数
    """
    matcher = SequenceMatcher(None, text1, text2)
    match = matcher.find_longest_match(0, len(text1), 0, len(text2))
    return match.size


def _compare_string_values(extracted_value: Any, standard_value: Any) -> bool:
    """
    比较两个字符串值是否相等
    
    比较策略：
    1. 如果都是金额/数字格式，只比较数字部分
    2. 如果标准值是长文本：
       a. 长度 > 50 时，整体相似度 >= 0.7 通过
       b. 长度 > 50 时，最长公共子串占标准文本比例 >= 0.6 通过
    3. 否则使用规范化后的严格相等比较
    
    Args:
        extracted_value: 提取的值
        standard_value: 标准值
        
    Returns:
        是否匹配
    """
    # 检查是否为金额或数字格式，如果是则只比较数字部分
    extracted_str = str(extracted_value)
    standard_str = str(standard_value)
    
    if _is_amount_or_number_format(extracted_str) and _is_amount_or_number_format(standard_str):
        # 提取并比较数字部分
        extracted_numeric = _extract_numeric_value(extracted_str)
        standard_numeric = _extract_numeric_value(standard_str)
        return extracted_numeric == standard_numeric
    
    # 否则进行文本比较
    # 规范化字符串
    normalized_extracted = _normalize_string(extracted_value)
    normalized_standard = _normalize_string(standard_value)
    
    # 以标准值的长度为判断依据
    standard_len = len(normalized_standard)
    
    # 策略1: 如果长度超过相似度阈值，尝试相似度比较
    if standard_len > TEXT_SIMILARITY_LENGTH_THRESHOLD:
        similarity = _calculate_text_similarity(normalized_extracted, normalized_standard)
        if similarity >= TEXT_SIMILARITY_THRESHOLD:
            return True
    
    # 策略2: 如果长度超过公共子串阈值，尝试公共子串比较
    # 注意：公共子串比较需要确保两个文本长度相近，避免短文本被包含在长文本中就判定为相等
    if standard_len > TEXT_OVERLAP_LENGTH_THRESHOLD:
        extracted_len = len(normalized_extracted)
        # 长度差异不能太大（允许 2 倍差异）
        length_ratio = max(standard_len, extracted_len) / min(standard_len, extracted_len) if min(standard_len, extracted_len) > 0 else float('inf')
        if length_ratio <= TEXT_OVERLAP_LENGTH_RATIO_THRESHOLD:
            overlap_length = _get_longest_common_substring_length(normalized_extracted, normalized_standard)
            overlap_ratio = overlap_length / standard_len if standard_len > 0 else 0
            if overlap_ratio >= TEXT_OVERLAP_RATIO_THRESHOLD:
                return True
    
    # 策略3: 短文本或以上策略都不通过时，使用严格相等比较
    return normalized_extracted == normalized_standard


def _compare_values(extracted_value: Any, standard_value: Any, expected_type: FieldType) -> bool:
        """
        比较两个值是否相等，考虑类型转换
        
        Args:
            extracted_value: 提取的值
            standard_value: 标准的值
            expected_type: 期望的类型
            
        Returns:
            两个值是否相等
        """
        # 如果两个值都是None，视为相等
        if extracted_value is None and standard_value is None:
            return True
        
        # 如果只有一个值是None，视为不相等
        if extracted_value is None or standard_value is None:
            return False
        
        try:
            # 根据期望类型进行比较
            if expected_type == FieldType.STRING:
                return _compare_string_values(extracted_value, standard_value)
            elif expected_type == FieldType.INTEGER:
                return int(extracted_value) == int(standard_value)
            elif expected_type == FieldType.FLOAT:
                # 对于浮点数，考虑精度问题
                return abs(float(extracted_value) - float(standard_value)) < 1e-6
            elif expected_type == FieldType.BOOLEAN:
                # 处理布尔值的多种表示形式
                extracted_bool = extracted_value
                standard_bool = standard_value
                return extracted_bool == standard_bool
            elif expected_type == FieldType.LIST or expected_type == FieldType.ARRAY:
                # 对于列表，检查元素是否相同（不考虑顺序）
                if not isinstance(extracted_value, list) or not isinstance(standard_value, list):
                    return False
                if len(extracted_value) != len(standard_value):
                    return False
                # 简单比较：转换为集合比较（适用于简单元素）
                return set(map(str, extracted_value)) == set(map(str, standard_value))
            else:
                # 默认情况下，直接比较字符串表示
                return str(extracted_value) == str(standard_value)
        except (ValueError, TypeError):
            # 如果转换失败，返回False
            return False
    
def _normalize_string(s: str, *, 
                      remove_punctuation: bool = False,
                      remove_whitespace: bool = True,
                      lowercase: bool = True,
                      remove_newline: bool = True,
                      ) -> str:
    """
    规范化字符串，用于比较
    
    Args:
        s: 待规范化的字符串
        remove_punctuation: 是否移除标点符号（默认False）
        remove_whitespace: 是否移除所有空白字符（默认True，会移除空格、换行、制表符等）
        lowercase: 是否转换为小写（默认True）
        remove_newline: 是否移除换行（默认True）
    
    Returns:
        规范化后的字符串
    
    Examples:
        >>> _normalize_string("  Hello World!  ")
        'helloworld!'
        >>> _normalize_string("测试\n文本", remove_whitespace=True)
        '测试文本'
        >>> _normalize_string("价格：100元", remove_punctuation=True)
        '价格100元'
    """
    if not isinstance(s, str):
        s = str(s)
    
    # 1. 去除首尾空格
    result = s.strip()
    
    # 2. 统一中英文标点（可选，便于后续处理）
    # 将常见中文标点转换为英文标点
    punctuation_map = {
        '，': ',', '。': '.', '；': ';', '：': ':', 
        '！': '!', '？': '?', '（': '(', '）': ')',
        '【': '[', '】': ']', '、': ',', '《': '<', '》': '>'
    }
    for cn, en in punctuation_map.items():
        result = result.replace(cn, en)
    
    # 3. 去除或规范化空白字符（换行、制表符、多个空格等）
    if remove_whitespace:
        # 移除所有空白字符
        result = re.sub(r'\s+', '', result)
    else:
        # 规范化空白字符：多个空白字符变成一个空格
        result = re.sub(r'\s+', ' ', result).strip()
    
    # 4. 移除标点符号（可选）
    if remove_punctuation:
        # 移除英文标点
        result = result.translate(str.maketrans('', '', string.punctuation))
        # 移除常见中文标点（如果没有在第2步转换的）
        cn_punctuation = '，。；：！？、《》【】''""（）…—·'
        result = result.translate(str.maketrans('', '', cn_punctuation))

    # 去除换行
    if remove_newline:
        result = result.replace('\n', '')
    
    # 5. 转换为小写（主要针对英文）
    if lowercase:
        result = result.lower()
    
    return result