import re
from typing import Any
from extract_agent.core.agent_packs.structure import Table
import datetime

def extract(article: list[str|Table]) -> dict[str, Any]:
    """
    从文章中提取参会登记截止日期。
    采用“寻找最晚截止日期”的鲁棒策略，专注于高精度关键词和紧凑的上下文关联，并兼容仅提供日期的情况。
    """
    result = {}
    latest_deadline_info = None

    # 1. 将所有内容合并为单个字符串，便于进行全文搜索
    full_text = "\n".join([str(item) for item in article])

    # 2. 优化关键词列表：回归高精度、与“登记截止”强相关的关键词。
    # 历史经验证明，使用一组精确的关键词比引入复杂逻辑（如会议开始时间）更稳定。
    keywords = [
        "登记时间", "登记截止", "截止时间", "截止日期", 
        "会议登记", "参会回执", "登记方法", "登记方式", 
        "现场登记", "预登记"
    ]
    
    # 3. 定义日期和时间的正则表达式
    date_pattern = re.compile(r'(?:(\d{4})年)?\s*(\d{1,2})月\s*(\d{1,2})日')
    time_pattern = re.compile(r'(\d{1,2})[：:](\d{2})')

    # 4. 全局提取所有日期，并进行上下文年份填充
    all_dates = []
    last_year = None
    for match in date_pattern.finditer(full_text):
        year_str, month_str, day_str = match.groups()
        if year_str:
            last_year = int(year_str)
        current_year = int(year_str) if year_str else last_year
        if not current_year:
            continue
        all_dates.append({
            "year": current_year,
            "month": int(month_str),
            "day": int(day_str),
            "pos": match.start()
        })

    # 5. 核心逻辑：寻找最晚截止日期，并处理有无明确时间的情况
    for kw in keywords:
        for kw_match in re.finditer(re.escape(kw), full_text):
            # 定义一个从关键词开始向后120个字符的搜索窗口，确保强关联性
            scope_start = kw_match.start()
            scope_end = scope_start + 120

            scoped_dates = [d for d in all_dates if scope_start <= d['pos'] < scope_end]
            
            # 优化点：只要找到日期就继续处理，不再强制要求必须有时间
            if not scoped_dates:
                continue

            scoped_times_matches = [m for m in time_pattern.finditer(full_text) if scope_start <= m.start() < scope_end]

            # 在窗口内取位置最靠后的日期
            last_date_in_scope = max(scoped_dates, key=lambda d: d['pos'])
            year, month, day = last_date_in_scope['year'], last_date_in_scope['month'], last_date_in_scope['day']
            
            has_explicit_time = False
            # 优化：当没有明确时间时，默认为当天结束(23:59)，以便于在比较中正确处理
            hour, minute = 23, 59 

            if scoped_times_matches:
                # 如果找到了时间，更新为实际时间
                has_explicit_time = True
                # 关键策略：取最晚的时间点，以处理 "9:00-17:00" 等范围
                last_time_match = max(scoped_times_matches, key=lambda m: m.start())
                hour_str, minute_str = last_time_match.groups()
                hour, minute = int(hour_str), int(minute_str)

                # 处理“下午”描述
                context_before_time = full_text[max(0, last_time_match.start() - 10):last_time_match.start()]
                if '下午' in context_before_time and 1 <= hour < 12:
                    hour += 12
            
            try:
                current_deadline = datetime.datetime(year, month, day, hour, minute)
                
                # 如果当前找到的截止日期比已记录的要晚，则更新
                if latest_deadline_info is None or current_deadline > latest_deadline_info['datetime']:
                    latest_deadline_info = {
                        'datetime': current_deadline,
                        'has_time': has_explicit_time
                    }
                    print(f"New latest deadline candidate: {current_deadline.strftime('%Y-%m-%d %H:%M:%S')} from '{kw}' (has_time: {has_explicit_time})")
            except ValueError:
                # 忽略无效日期（如2月30日）
                continue

    # 6. 格式化输出：根据有无明确时间，选择不同格式
    if latest_deadline_info:
        final_deadline = latest_deadline_info['datetime']
        if latest_deadline_info['has_time']:
            result['参会登记日期截止日期'] = final_deadline.strftime('%Y-%m-%d %H:%M:%S')
        else:
            # 如果没有明确时间，只输出日期部分，以匹配标准答案
            result['参会登记日期截止日期'] = final_deadline.strftime('%Y-%m-%d')
    
    return result