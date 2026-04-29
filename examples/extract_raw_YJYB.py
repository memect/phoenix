from typing import Any
from extract_agent.core.agent_packs.structure import Table
def extract(article: list[str|Table]) -> dict[str, Any]:
    result = {
        '本期扣非前净利润上限（万元）': None
    }
    for item in article:
        if isinstance(item, Table):
            ...
        else:
            ...
    return result