from typing import Any
from extract_agent.core.agent_packs.structure import Table
def extract(article: list[str|Table]) -> list[dict[str, Any]]:
    result = []
    for item in article:
        if isinstance(item, Table):
            ...
        else:
            ...
    return result