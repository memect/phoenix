from typing import Any
from extract_agent.core.agent_packs.structure import Chapter
from extract_agent.core.agent_packs.structure import Table
import re

def find_chapters(article: Chapter, title_patterns: list[str]) -> list[Chapter]:
    """
    递归查找标题匹配给定模式的章节。
    """
    ret = []
    for chapter in article.children:
        for title_pattern in title_patterns:
            if re.search(title_pattern, chapter.title):
                ret.append(chapter)
                break
        ret.extend(find_chapters(chapter, title_patterns))
    return ret


def extract(article: Chapter) -> dict[str, Any]:
    """
    从文章中提取会议召开地点。
    """
    result = {
        '会议召开地点': None
    }

    # 1. 定位主章节（使用更通用的模式）
    # 优化点1：放宽章节定位的正则表达式，兼容“股东大会”、“本次”等情况
    main_chapter_pattern = r"(?:股东大会|会议).*(?:召开)?.*基本情况"
    main_chapters = find_chapters(article, [main_chapter_pattern])
    print(f"Found {len(main_chapters)} main chapters for meeting location using pattern: '{main_chapter_pattern}'")

    if not main_chapters:
        # 如果找不到主章节，尝试一个更宽泛的备用模式，以防万一
        main_chapters = find_chapters(article, [r"会议.*基本情况"])
        print(f"Fallback: Found {len(main_chapters)} main chapters using pattern: '会议.*基本情况'")


    # 2. 定义用于提取信息的正则表达式
    location_pattern = re.compile(r"(?:现场)?会议(?:召开)?地点[:：]\s*(.*)")
    # 优化点2.1：新增“会议地址”的匹配模式
    address_pattern = re.compile(r"会议地址[:：]\s*(.*)")

    for chapter in main_chapters:
        # 优化点2.2：使用变量存储可能拆分的地址信息，而不是找到即返回
        location_part = None
        address_part = None

        # 搜集章节内所有待检索的文本（子章节标题和段落）
        texts_to_search = []
        for sub_chapter in chapter.children:
            texts_to_search.append(sub_chapter.title)
        for content in chapter.contents:
            if isinstance(content, str):
                texts_to_search.append(content)
        
        # 遍历所有文本，提取“会议地点”和“会议地址”
        for text in texts_to_search:
            loc_match = location_pattern.search(text)
            if loc_match:
                # 清洗并暂存“会议地点”
                cleaned_loc = loc_match.group(1).strip().strip('。')
                if cleaned_loc:
                    location_part = cleaned_loc

            addr_match = address_pattern.search(text)
            if addr_match:
                # 清洗并暂存“会议地址”
                cleaned_addr = addr_match.group(1).strip().strip('。')
                if cleaned_addr:
                    address_part = cleaned_addr
        
        # 优化点2.3：在扫描完整个章节后，智能组合地址信息
        final_location = None
        if address_part and location_part:
            # 如果两部分都存在，组合它们（通常地址在前，地点在后）
            # 避免重复拼接
            if location_part.startswith(address_part):
                 final_location = location_part
            elif address_part.endswith(location_part):
                 final_location = address_part
            else:
                 final_location = address_part + location_part
        elif location_part:
            # 仅存在“会议地点”
            final_location = location_part
        elif address_part:
            # 仅存在“会议地址”
            final_location = address_part

        if final_location:
            result['会议召开地点'] = final_location
            print(f"Extracted location parts: address='{address_part}', location='{location_part}'")
            print(f"Final combined location: {final_location}")
            return result # 找到完整地址后返回

    return result