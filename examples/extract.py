from typing import Any
from extract_agent.core.agent_packs.structure import Table
import re

def extract(article: list[str|Table]) -> dict[str, Any]:
    result = {}
    location_parts = {}

    for i, item in enumerate(article):
        if isinstance(item, str):
            # 寻找“会议地点”
            match_loc = re.search(r'会议(?:召开)?地点[:：\s]*(.*)', item)
            if match_loc:
                loc_val = match_loc.group(1).strip(' :：。，')
                if loc_val:
                    location_parts['location'] = loc_val
                # 如果地点后面没有内容，则尝试查看下一个元素
                elif i + 1 < len(article) and isinstance(article[i+1], str):
                    next_item_val = article[i+1].strip(' :：。，')
                    if next_item_val:
                        location_parts['location'] = next_item_val

            # 寻找“会议地址”
            match_addr = re.search(r'会议地址[:：\s]*(.*)', item)
            if match_addr:
                addr_val = match_addr.group(1).strip(' :：。，')
                if addr_val:
                    location_parts['address'] = addr_val

        elif isinstance(item, Table):
            for cell in item.cells:
                if "会议地点" in cell.text or "会议召开地点" in cell.text:
                    right_neighbors = item.get_right_neighbor(cell)
                    if right_neighbors:
                        val = right_neighbors[0].text.strip(' :：。，')
                        if val:
                            location_parts['location'] = val
                            break
                    down_neighbors = item.get_down_neighbor(cell)
                    if down_neighbors:
                        val = down_neighbors[0].text.strip(' :：。，')
                        if val:
                            location_parts['location'] = val
                            break
            if 'location' in location_parts:
                continue

    # 组合地址和地点
    final_location = []
    if 'address' in location_parts:
        final_location.append(location_parts['address'])
    if 'location' in location_parts:
        # 避免重复
        if location_parts['location'] not in final_location:
            final_location.append(location_parts['location'])
    
    if final_location:
        result["会议召开地点"] = "".join(final_location)

    return result