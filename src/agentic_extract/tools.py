"""
文件写入工具

支持可选的行数限制模式。
"""

from agentscope.tool import Toolkit, write_text_file, insert_text_file


def create_file_tools(
    limit_write_lines: bool = False,
    max_write_lines: int = 100,
) -> tuple:
    """
    创建文件工具

    Args:
        limit_write_lines: 是否启用行数限制模式
        max_write_lines: 每次写入的最大行数

    Returns:
        (write_text_file, insert_text_file) 元组
    """
    # 如果不需要行数限制，直接返回原生工具
    if not limit_write_lines:
        return write_text_file, insert_text_file

    # 构建带行数限制提示的 docstring
    write_doc = f"""Create/Replace/Overwrite content in a text file. When `ranges` is provided, the content will be replaced in the specified range. Otherwise, the entire file (if exists) will be overwritten.

**IMPORTANT: 每次最多写入 {max_write_lines} 行。** 超过时请分批写入：
1. 先用此工具写入前 {max_write_lines} 行
2. 用 insert_text_file 追加剩余内容

Args:
    file_path (`str`):
        The target file path.
    content (`str`):
        The content to be written.
    ranges (`list[int] | None`, defaults to `None`):
        The range of lines to be replaced. If `None`, the entire file will
        be overwritten.

Returns:
    `ToolResponse`:
        The tool response containing the result of the writing operation.
"""

    insert_doc = f"""Insert the content at the specified line number in a text file.

**IMPORTANT: 每次最多插入 {max_write_lines} 行。** 超过时请分批插入。

Args:
    file_path (`str`):
        The target file path.
    content (`str`):
        The content to be inserted.
    line_number (`int`):
        The line number at which the content should be inserted, starting
        from 1. If exceeds the number of lines in the file, it will be
        appended to the end of the file.

Returns:
    `ToolResponse`:
        The tool response containing the result of the insertion operation.
"""

    # 创建带自定义 docstring 的包装函数
    async def write_text_file_limited(file_path: str, content: str, ranges: None | list[int] = None):
        return await write_text_file(file_path, content, ranges)

    async def insert_text_file_limited(file_path: str, content: str, line_number: int):
        return await insert_text_file(file_path, content, line_number)

    write_text_file_limited.__doc__ = write_doc
    insert_text_file_limited.__doc__ = insert_doc

    return write_text_file_limited, insert_text_file_limited


def register_file_tools(
    toolkit: Toolkit,
    limit_write_lines: bool = False,
    max_write_lines: int = 100,
) -> None:
    """
    注册文件写入工具到 Toolkit

    Args:
        toolkit: 要注册工具的 Toolkit 实例
        limit_write_lines: 是否启用行数限制模式
        max_write_lines: 每次写入最大行数
    """
    write_tool, insert_tool = create_file_tools(
        limit_write_lines=limit_write_lines,
        max_write_lines=max_write_lines,
    )
    toolkit.register_tool_function(write_tool)
    toolkit.register_tool_function(insert_tool)
