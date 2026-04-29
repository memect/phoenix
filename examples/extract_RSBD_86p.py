import re
from typing import Any
from extract_agent.core.agent_packs.structure import Table
from extract_agent.core.agent_packs.get_tools import create_default_tool_hub

def extract(article: list[str|Table]) -> list[dict[str, Any]]:
    tool_hub = create_default_tool_hub()
    ner_tool = tool_hub.get_tool('ner_regex_tool')
    
    org_name = None
    
    # Pass 1: Find Organization Name
    # Search for the most likely candidate for the organization name.
    for item in article:
        if isinstance(item, str):
            # A more specific regex to find company names, often appearing at the end of a line or followed by "董事会"
            match = re.search(r'([\s\S]*?(?:股份有限公司|有限公司))', item)
            if match:
                # Clean up the matched name
                potential_name = match.group(1).strip()
                # Avoid overly long matches that might be entire paragraphs
                if len(potential_name) < 100:
                    org_name = potential_name
                    break
    
    if not org_name:
        return []

    # Pass 2: Extract all potential candidates from the entire document
    all_results = []
    pattern = r'(?P<name>{@<PER>.*?@})(?P<salutation>先生|女士|同志)'
    
    for item in article:
        if isinstance(item, str):
            # Skip very short strings which are unlikely to contain full context
            if len(item.strip()) < 5:
                continue
            
            matches = ner_tool.finditer(pattern, item)
            for match in matches:
                person_name = match.group('name').strip()
                # Basic name validation
                if len(person_name) < 2 or len(person_name) > 4:
                    continue
                
                salutation = match.group('salutation').strip()
                result = {
                    "原文_人名": person_name,
                    "原文_称呼": salutation,
                    "原文_机构名": org_name
                }
                # Avoid duplicates
                if result not in all_results:
                    all_results.append(result)

    # Final Pass: Filter out names that are substrings of other found names
    if not all_results:
        return []

    final_results = []
    names_found = {res['原文_人名'] for res in all_results}
    
    for res in all_results:
        is_substring = False
        current_name = res['原文_人名']
        for name in names_found:
            if current_name != name and current_name in name:
                is_substring = True
                break
        if not is_substring:
            final_results.append(res)

    return final_results