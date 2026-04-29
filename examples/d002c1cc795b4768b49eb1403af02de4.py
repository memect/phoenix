from typing import Any
from extract_agent.core.agent_packs.structure import Table
import re

def extract(article: list[str|Table]) -> dict[str, Any] | list[dict[str, Any]]:
    """
    从公告中提取注册资本变更信息。
    """
    results = []
    
    extracted_data = {
        "原文_公司名称": None,
        "原文_原注册资本": None,
        "原文_现注册资本": None,
        "原文_增加额": None
    }

    # --- 1. 正则表达式优化 ---

    # 优化后的金额模式，更灵活，支持多种单位和格式
    amount_pattern = r"((?:人民币|美元)?\s*[\d,./\s亿万仟佰拾玖捌柒陆伍肆叁贰壹元整]+(?:元|万元|万|亿元|亿)?)"
    # 用于表格的宽松金额模式，可匹配不带单位的纯数字
    table_amount_pattern = r"([\d,./]+)"

    # 模式1 (最高优先级): 捕获 "由/从 A 变为/增加至/增加为/增至 B" 的句式
    # 增强点: 支持 "将由", "从", 允许中间出现 "人民币"
    capital_change_pattern_1 = re.compile(
        r"(?:的)?注册资本\s*(?:将?由|从)\s*(?:人民币|美元)?\s*" + amount_pattern + r"\s*(?:增加至|变更为|增加为|增至)\s*" + amount_pattern
    )
    
    # 模式2: 捕获 "增加至/增至 B" 的句式，用于补充提取 "现注册资本"
    # 增强点: 支持 "增至"
    capital_change_pattern_2 = re.compile(r"注册资本将?(?:增加至|增至)\s*" + amount_pattern)

    # 模式3: 捕获 "原为 A，现为 B" 的句式 (常见于《公司章程》修订)
    capital_change_pattern_3 = re.compile(r"《公司章程》原.*?注册资本为" + amount_pattern + r"。\s*现修改为：\s*.*?注册资本为" + amount_pattern)

    # 强特征公司名称模式: "公司名称：" 等
    # 增强点: 捕获组 `(.+?)` 配合 `(?:\n|$)` 可完整匹配带括号的公司名
    strong_company_name_pattern = re.compile(r"(?:公司名称|投资标的名称|企业全称)\s*[:：]\s*(.+?)(?:\n|$)")
    
    # 上下文公司名称模式: "对子公司 XXX(公司) 进行增资"
    # 增强点: 更精确地匹配以 "公司" 结尾的实体
    context_company_name_pattern = re.compile(r"(?:对|向)(?:全资|控股)?子公司\s*([\u4e00-\u9fa5]+(?:（[^）]+）)?(?:有限公司|股份有限公司))")

    # 弱特征公司名称模式: "...股份有限公司" 或 "...有限公司"
    weak_company_name_pattern = re.compile(r"([\u4e00-\u9fa5]+(?:股份有限公司|（集团）股份有限公司|集团股份有限公司|有限公司))")

    # 单独的注册资本信息: "注册资本："
    current_capital_pattern = re.compile(r"注册资本\s*[:：]\s*" + amount_pattern)

    full_text = "\n".join([str(item) for item in article])

    # --- 2. 提取逻辑重构 (按优先级) ---

    # 优先级1: 从最明确的资本变更句式中提取资本信息
    text_capital_info = {}
    match1 = capital_change_pattern_1.search(full_text)
    if match1:
        text_capital_info["原文_原注册资本"] = match1.group(1).strip()
        text_capital_info["原文_现注册资本"] = match1.group(2).strip()
    else:
        match3 = capital_change_pattern_3.search(full_text)
        if match3:
            text_capital_info["原文_原注册资本"] = match3.group(1).strip()
            text_capital_info["原文_现注册资本"] = match3.group(2).strip()
    
    # 优先级2: 从表格中提取资本信息
    table_capital_info = {}
    for item in article:
        if isinstance(item, Table) and item.row_num > 1:
            header = item.table_data[0]
            before_col, after_col = -1, -1
            for i, cell in enumerate(header):
                cell_text = cell.text.strip()
                if any(k in cell_text for k in ["前", "原条款", "原有内容"]) and "后" not in cell_text:
                    before_col = i
                if any(k in cell_text for k in ["后", "修订", "修订内容"]) and "前" not in cell_text:
                    after_col = i

            if before_col != -1 and after_col != -1:
                for row_index in range(1, item.row_num):
                    row = item.table_data[row_index]
                    if len(row) > max(before_col, after_col) and "注册资本" in "".join([c.text for c in row]):
                        before_cell_text = row[before_col].text
                        after_cell_text = row[after_col].text
                        
                        before_match = re.search(amount_pattern, before_cell_text) or re.search(table_amount_pattern, before_cell_text)
                        after_match = re.search(amount_pattern, after_cell_text) or re.search(table_amount_pattern, after_cell_text)
                        
                        if before_match:
                            table_capital_info["原文_原注册资本"] = before_match.group(1).strip()
                        if after_match:
                            table_capital_info["原文_现注册资本"] = after_match.group(1).strip()
                        break # 找到注册资本行就停止

    # 优先级3: 提取公司名称
    # 策略: 强特征 > 上下文 > 弱特征
    strong_company_match = strong_company_name_pattern.search(full_text)
    if strong_company_match:
        extracted_data["原文_公司名称"] = strong_company_match.group(1).strip()
    
    if not extracted_data["原文_公司名称"]:
        context_company_match = context_company_name_pattern.search(full_text)
        if context_company_match:
            extracted_data["原文_公司名称"] = context_company_match.group(1).strip()

    if not extracted_data["原文_公司名称"]:
        for item in article:
            if isinstance(item, str) and ("注册资本" in item and ("增加" in item or "变更" in item)):
                weak_company_match = weak_company_name_pattern.search(item)
                if weak_company_match and "简称" not in item and "本公司" not in item and "公司" in weak_company_match.group(1):
                    extracted_data["原文_公司名称"] = weak_company_match.group(1).strip()
                    break

    # 优先级4: 使用后备模式补充资本信息
    supplementary_capital_info = {}
    for item in article:
        if isinstance(item, str):
            match2 = capital_change_pattern_2.search(item)
            if match2:
                supplementary_capital_info["原文_现注册资本"] = match2.group(1).strip()
            
            current_match = current_capital_pattern.search(item)
            if current_match:
                capital_value = current_match.group(1).strip()
                if ("基本情况" in item or "变更前" in item) and "原文_原注册资本" not in supplementary_capital_info:
                    supplementary_capital_info["原文_原注册资本"] = capital_value
                elif "变更后" in item and "原文_现注册资本" not in supplementary_capital_info:
                    supplementary_capital_info["原文_现注册资本"] = capital_value
                elif "原文_原注册资本" not in supplementary_capital_info:
                     supplementary_capital_info["原文_原注册资本"] = capital_value

    # --- 3. 数据填充与整合 (按优先级覆盖) ---
    # 规则: 补充信息 < 表格信息 < 明确文本信息
    extracted_data.update(supplementary_capital_info)
    extracted_data.update(table_capital_info)
    extracted_data.update(text_capital_info)

    # --- 4. 最终清理与输出 ---
    if any(value is not None for key, value in extracted_data.items() if key != "原文_增加额"):
        for key, value in extracted_data.items():
            if isinstance(value, str):
                cleaned_value = value.strip().rstrip('。，、')
                # 避免过度清理，仅当"人民币"不是唯一内容时移除
                if "人民币" in cleaned_value and len(cleaned_value.replace("人民币", "").strip()) > 0:
                     cleaned_value = cleaned_value.replace("人民币", "").strip()
                extracted_data[key] = cleaned_value
        
        results.append(extracted_data)
        print(f"Extracted data: {extracted_data}")

    return results if results else None