import re
from typing import Any, Optional, Dict, Tuple, List
from extract_agent.core.agent_packs.structure import Table, Cell

def _find_header_indices(table: Table) -> Optional[Tuple[Dict[str, int], int]]:
    """
    Finds the column indices for key headers and the last row index of the header section.
    It handles multi-row headers and prioritizes exact matches.
    Returns: A tuple (indices_dict, header_last_row_idx) or None.
    """
    header_keywords = {
        'proposal_id': ['提案编码', '议案编码'],
        'proposal_name': ['提案名称', '议案名称', '提案事项'],
        'remark': ['备注']
    }
    indices = {}
    header_last_row_idx = -1

    # Search in the first few rows for headers
    for row_idx in range(min(5, table.row_num)):
        row_cells = table.table_data[row_idx]
        found_in_row = False
        for cell in row_cells:
            cell_text = cell.text.strip()
            if not cell_text:
                continue
            for key, keywords in header_keywords.items():
                if key in indices:
                    continue
                # Prioritize exact match
                if any(keyword == cell_text for keyword in keywords):
                    indices[key] = cell.col_index
                    found_in_row = True
                    break
                # Fallback to partial match for complex headers
                if any(keyword in cell_text for keyword in keywords):
                    indices[key] = cell.col_index
                    found_in_row = True
                    break
        
        if found_in_row:
            header_last_row_idx = row_idx

        # Stop if essential headers are found
        if 'proposal_id' in indices and 'proposal_name' in indices:
            break
            
    if 'proposal_id' in indices and 'proposal_name' in indices:
        print(f"Found headers at indices: {indices}, header ends at row: {header_last_row_idx}")
        return indices, header_last_row_idx
        
    return None

def _clean_proposal_name(text: str) -> str:
    """
    Cleans the proposal name by removing specific prefixes, trailing punctuations, and obvious repeated words.
    """
    # Remove prefixes like "议案一：", "提案1、" etc.
    cleaned_text = re.sub(r'^((?:议案|提案)(?:[一二三四五六七八九十]+|[0-9]+)[:：、]?\s*)', '', text.strip())
    # Remove trailing punctuations like '；', '。', ';', '.'
    cleaned_text = cleaned_text.rstrip('；。;.')
    # Fix obvious repeated words like "第第七届" -> "第七届" by matching any repeated sequence of 2+ chars
    cleaned_text = re.sub(r'(.{2,})\1+', r'\1', cleaned_text)
    return cleaned_text

def _normalize_proposal_id(id_str: str) -> str:
    """
    Normalizes the proposal ID.
    - Removes '.00' suffix (e.g., '1.00' -> '1').
    - Standardizes sub-proposal IDs (e.g., '12.01' -> '12.1').
    """
    if id_str.endswith('.00'):
        return id_str[:-3]
    return re.sub(r'\.0(\d)$', r'.\1', id_str)

def _parse_remark(remark_text: str, context: Dict[str, Any]) -> Tuple[str, str]:
    """
    Parses the remark column and uses global context to determine voting rules.
    Priority Order: 1. Explicit remark text > 2. Global context > 3. Default.
    """
    remark_text = remark_text.strip()
    
    # Priority 1: Explicit text in remark column (most specific)
    match = re.search(r'(?:应选|选举|应选人数)[（(]?(\d+)[)）]?人?', remark_text)
    if match:
        return '是', match.group(1)
    
    if '不适用' in remark_text:
        return '否', ''

    # Priority 2: Global context from surrounding text
    if context.get('is_cumulative') == '是':
        return '是', context.get('elected_count', '')
    if context.get('is_cumulative') == '否':
        return '否', ''
        
    # Priority 3: Default to non-cumulative (handles '√' and empty remarks)
    return '否', ''

def _is_valid_proposal_row(proposal_id: str, proposal_name: str) -> bool:
    """
    Validates if the extracted row is a legitimate proposal.
    """
    if not proposal_name:
        return False
    # Filter out rows where proposal name is the same as the ID (parsing error)
    if proposal_name == proposal_id:
        return False
    # Filter out separator rows
    summary_keywords = ['投票提案', '投票议案']
    if any(kw in proposal_name for kw in summary_keywords):
        return False
    return True

def _get_global_context(article: list[str|Table]) -> Dict[str, Dict[str, Any]]:
    """Scans non-table text to find global rules about voting."""
    context_map = {}
    for item in article:
        if isinstance(item, str):
            # Pattern for "议案X、Y采用累积投票...应选Z人"
            cumulative_matches = re.finditer(r'议案\s?([\d\s、,，和]+)\s?.*?采用累积投票制.*?应选.*?(\d+)\s?人', item)
            for match in cumulative_matches:
                ids_str, count = match.groups()
                ids = re.findall(r'\d+', ids_str)
                for proposal_id in ids:
                    normalized_id = _normalize_proposal_id(proposal_id)
                    context_map[normalized_id] = {'is_cumulative': '是', 'elected_count': count}
                    print(f"Global context: Proposal {normalized_id} is cumulative, count {count}.")

            # Pattern for "议案X...不适用累积投票制"
            non_cumulative_matches = re.finditer(r'(?:议案|提案)\s?(\d+[\.\d]*).*?(不适用累积投票制)', item)
            for match in non_cumulative_matches:
                proposal_id, _ = match.groups()
                normalized_id = _normalize_proposal_id(proposal_id)
                if normalized_id not in context_map: # Avoid overwriting more specific cumulative info
                    context_map[normalized_id] = {'is_cumulative': '否'}
                    print(f"Global context: Proposal {normalized_id} is non-cumulative.")
    return context_map

def extract(article: list[str|Table]) -> list[Dict[str, Any]]:
    """
    Extracts proposal information from tables within the article, leveraging global context
    from text and robustly handling various table structures.
    """
    result = []
    processed_proposal_ids = set()
    global_context = _get_global_context(article)

    for item in article:
        if not isinstance(item, Table):
            continue

        header_info = _find_header_indices(item)
        if not header_info:
            continue
        
        header_indices, header_last_row_idx = header_info
        id_col_idx = header_indices.get('proposal_id')
        name_col_idx = header_indices.get('proposal_name')
        remark_col_idx = header_indices.get('remark')

        cumulative_vote_status: Dict[str, Tuple[str, str]] = {}
        
        # Start scanning from the row after the header
        for row_idx in range(header_last_row_idx + 1, item.row_num):
            row_data = item.table_data[row_idx]
            
            proposal_id_cell = next((c for c in row_data if c.col_index == id_col_idx), None)
            # Flexible check for proposal ID using search instead of fullmatch
            if not proposal_id_cell:
                continue
            id_match = re.search(r'^\s*(\d+(\.\d+)?)\s*', proposal_id_cell.text)
            if not id_match:
                continue
            proposal_id_str = id_match.group(1)

            proposal_name_cell = next((c for c in row_data if c.col_index == name_col_idx), None)
            if not proposal_name_cell:
                continue
            
            proposal_name_str = proposal_name_cell.text.strip()

            if not _is_valid_proposal_row(proposal_id_str, proposal_name_str):
                continue

            # Enhanced filter for summary/total proposals
            summary_keywords = ['总议案', '所有提案', '所有议案', '除累积投票', '总提案']
            if proposal_id_str == '100' and any(kw in proposal_name_str for kw in summary_keywords):
                continue

            normalized_id = _normalize_proposal_id(proposal_id_str)
            if normalized_id in processed_proposal_ids:
                continue
            
            proposal_name = _clean_proposal_name(proposal_name_str)
            
            remark_text = ''
            if remark_col_idx is not None:
                remark_cell = next((c for c in row_data if c.col_index == remark_col_idx), None)
                if remark_cell:
                    remark_text = remark_cell.text

            # Get context for this specific proposal
            prop_context = global_context.get(normalized_id, {})
            is_cumulative, elected_count = _parse_remark(remark_text, prop_context)
            
            main_proposal_id = normalized_id.split('.')[0]

            # Inherit cumulative status for sub-proposals
            if '.' in normalized_id and main_proposal_id in cumulative_vote_status:
                is_cumulative = cumulative_vote_status[main_proposal_id][0]
                elected_count = '' # Sub-proposals don't have their own elected count
            # Store status for main cumulative proposals
            elif '.' not in normalized_id and is_cumulative == '是':
                cumulative_vote_status[main_proposal_id] = (is_cumulative, elected_count)

            proposal_info = {
                '议案序号': normalized_id,
                '议案内容': proposal_name,
                '累计投票制是否适用': is_cumulative,
                '应选人数': elected_count,
            }
            
            result.append(proposal_info)
            processed_proposal_ids.add(normalized_id)
        
        # If we found results in this table, assume it's the correct one and stop.
        if result:
            print(f"Successfully extracted {len(result)} proposals from the first valid table. Stopping.")
            break
            
    print(f"Extracted {len(result)} proposals in total.")
    return result