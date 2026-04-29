"""
Tree-sitter CLI 工具

提供代码结构分析和符号查找功能。

使用方式：
    tree-sitter-cli analyze <file>
    tree-sitter-cli find-symbol <file> <symbol_name>
    tree-sitter-cli list-symbols <file>
"""

import json
import sys
from pathlib import Path

import typer

try:
    import tree_sitter_python as tspython
    from tree_sitter import Language, Parser, Node
except ImportError:
    print("Error: tree-sitter and tree-sitter-python are required.")
    print("Install with: pip install tree-sitter tree-sitter-python")
    sys.exit(1)


app = typer.Typer(help="Tree-sitter 代码分析工具")

# 初始化 Python 解析器
PY_LANGUAGE = Language(tspython.language())


def create_parser() -> Parser:
    """创建 Python 解析器"""
    parser = Parser(PY_LANGUAGE)
    return parser


def get_node_text(node: Node, source_bytes: bytes) -> str:
    """获取节点的源代码文本"""
    return source_bytes[node.start_byte:node.end_byte].decode('utf-8')


# 长度阈值：超过此长度的值会被省略
_MAX_VALUE_LENGTH = 60


def _should_abbreviate_value(node: Node, source_bytes: bytes) -> bool:
    """判断值是否应该被省略"""
    if node.type in ("string", "concatenated_string"):
        return True  # 字符串总是省略
    text = get_node_text(node, source_bytes)
    return len(text) > _MAX_VALUE_LENGTH or "\n" in text


def _get_type_hint(node: Node, source_bytes: bytes) -> str | None:
    """从类型注解节点获取类型字符串"""
    for child in node.children:
        if child.type == "type":
            return get_node_text(child, source_bytes)
    return None


def _extract_assignment_skeleton(node: Node, source_bytes: bytes) -> str | None:
    """
    提取赋值语句骨架，省略长值
    
    支持的形式：
    - x = value
    - x: type = value
    - x, y = value
    """
    # 找到赋值的左侧和右侧
    left_parts = []
    type_hint = None
    right_node = None
    
    children = list(node.children)
    i = 0
    while i < len(children):
        child = children[i]
        if child.type == "identifier":
            left_parts.append(get_node_text(child, source_bytes))
        elif child.type == "pattern_list":
            # 多变量赋值 a, b = ...
            names = []
            for pc in child.children:
                if pc.type == "identifier":
                    names.append(get_node_text(pc, source_bytes))
            left_parts.append(", ".join(names))
        elif child.type == "type":
            type_hint = get_node_text(child, source_bytes)
        elif child.type == ":" and i + 1 < len(children) and children[i + 1].type == "type":
            # 跳过冒号，下一个循环会处理 type
            pass
        elif child.type not in ("=", ":"):
            # 这是右侧的值
            right_node = child
        i += 1
    
    if not left_parts:
        return None
    
    left_str = left_parts[0]
    if type_hint:
        left_str = f"{left_str}: {type_hint}"
    
    # 判断是否需要省略右侧值
    if right_node and _should_abbreviate_value(right_node, source_bytes):
        return f"{left_str} = ..."
    elif right_node:
        return f"{left_str} = {get_node_text(right_node, source_bytes)}"
    else:
        return left_str


def extract_skeleton(node: Node, source_bytes: bytes, indent: int = 0) -> list[str]:
    """
    提取代码骨架，省略函数体和注释
    
    返回代码行列表
    """
    lines = []
    indent_str = "    " * indent
    
    if node.type == "module":
        # 模块级别：在不同类型的元素之间添加空行
        prev_type = None
        for child in node.children:
            child_lines = extract_skeleton(child, source_bytes, indent)
            if child_lines:
                curr_type = _get_element_category(child)
                # 在不同类别之间添加空行
                if prev_type and curr_type and prev_type != curr_type:
                    lines.append("")
                # 在类/函数之前添加空行（除非是第一个元素）
                elif prev_type and curr_type in ("class", "function"):
                    lines.append("")
                lines.extend(child_lines)
                prev_type = curr_type
    
    elif node.type == "class_definition":
        # 提取类定义行
        class_line_parts = []
        for child in node.children:
            if child.type == "class":
                class_line_parts.append("class")
            elif child.type == "identifier":  # 类名是 identifier 类型
                class_line_parts.append(get_node_text(child, source_bytes))
            elif child.type == "argument_list":
                class_line_parts.append(get_node_text(child, source_bytes))
            elif child.type == ":":
                class_line_parts.append(":")
                break
        
        lines.append(f"{indent_str}{' '.join(class_line_parts)}")
        
        # 处理类体
        for child in node.children:
            if child.type == "block":
                for block_child in child.children:
                    lines.extend(extract_skeleton(block_child, source_bytes, indent + 1))
    
    elif node.type == "function_definition":
        # 提取函数签名
        func_parts = []
        has_async = False
        for child in node.children:
            if child.type == "async":
                has_async = True
            elif child.type == "def":
                if has_async:
                    func_parts.append("async def")
                else:
                    func_parts.append("def")
            elif child.type == "identifier":  # 函数名是 identifier 类型
                func_parts.append(get_node_text(child, source_bytes))
            elif child.type == "parameters":
                func_parts.append(get_node_text(child, source_bytes))
            elif child.type == "->":
                func_parts.append("->")
            elif child.type == "type":
                # 返回类型注解
                func_parts.append(get_node_text(child, source_bytes))
            elif child.type == ":":
                func_parts.append(":")
                break
        
        lines.append(f"{indent_str}{' '.join(func_parts)} ...")
    
    elif node.type == "decorated_definition":
        # 处理装饰器
        for child in node.children:
            if child.type == "decorator":
                decorator_text = get_node_text(child, source_bytes)
                lines.append(f"{indent_str}{decorator_text}")
            elif child.type in ("function_definition", "class_definition"):
                lines.extend(extract_skeleton(child, source_bytes, indent))
    
    elif node.type == "import_statement" or node.type == "import_from_statement":
        # 保留 import 语句
        lines.append(f"{indent_str}{get_node_text(node, source_bytes)}")
    
    elif node.type == "expression_statement":
        # 检查是否是模块级别的赋值（如全局变量）
        for child in node.children:
            if child.type == "assignment":
                # 提取赋值语句骨架，省略长字符串值
                assignment_skeleton = _extract_assignment_skeleton(child, source_bytes)
                if assignment_skeleton:
                    lines.append(f"{indent_str}{assignment_skeleton}")
                break
            elif child.type == "string":
                # 可能是 docstring，跳过
                pass
    
    elif node.type == "if_statement" and indent == 0:
        # 顶层的 if __name__ == "__main__"
        condition_text = ""
        for child in node.children:
            if child.type == "comparison_operator":
                condition_text = get_node_text(child, source_bytes)
                break
        if "__name__" in condition_text and "__main__" in condition_text:
            lines.append(f'{indent_str}if __name__ == "__main__": ...')
    
    return lines


def _get_element_category(node: Node) -> str | None:
    """获取节点的元素类别，用于决定是否添加空行"""
    if node.type in ("import_statement", "import_from_statement"):
        return "import"
    elif node.type == "class_definition":
        return "class"
    elif node.type == "function_definition":
        return "function"
    elif node.type == "decorated_definition":
        # 查看装饰器下的实际定义
        for child in node.children:
            if child.type == "class_definition":
                return "class"
            elif child.type == "function_definition":
                return "function"
        return "function"  # 默认
    elif node.type == "expression_statement":
        for child in node.children:
            if child.type == "assignment":
                return "variable"
        return None
    elif node.type == "if_statement":
        return "main"
    return None


def find_symbols(node: Node, source_bytes: bytes, target_name: str | None = None) -> list[dict]:
    """
    查找符号定义
    
    Args:
        node: AST 节点
        source_bytes: 源代码字节
        target_name: 要查找的符号名，None 表示返回所有符号
    
    Returns:
        符号信息列表
    """
    symbols = []
    
    def visit(n: Node, parent_class: str | None = None):
        if n.type == "class_definition":
            name_node = None
            for child in n.children:
                if child.type == "identifier":  # 类名是 identifier 类型
                    name_node = child
                    break
            
            if name_node:
                class_name = get_node_text(name_node, source_bytes)
                if target_name is None or class_name == target_name:
                    symbols.append({
                        "name": class_name,
                        "type": "class",
                        "line": n.start_point[0] + 1,
                        "end_line": n.end_point[0] + 1,
                    })
                
                # 继续遍历类体，记录方法
                for child in n.children:
                    if child.type == "block":
                        for block_child in child.children:
                            visit(block_child, class_name)
        
        elif n.type == "function_definition":
            name_node = None
            for child in n.children:
                if child.type == "identifier":  # 函数名是 identifier 类型
                    name_node = child
                    break
            
            if name_node:
                func_name = get_node_text(name_node, source_bytes)
                full_name = f"{parent_class}.{func_name}" if parent_class else func_name
                
                if target_name is None or func_name == target_name or full_name == target_name:
                    symbol_type = "method" if parent_class else "function"
                    symbols.append({
                        "name": full_name if parent_class else func_name,
                        "type": symbol_type,
                        "line": n.start_point[0] + 1,
                        "end_line": n.end_point[0] + 1,
                    })
        
        elif n.type == "decorated_definition":
            for child in n.children:
                if child.type in ("function_definition", "class_definition"):
                    visit(child, parent_class)
        
        elif n.type == "assignment":
            # 全局变量或类属性
            for child in n.children:
                if child.type == "identifier":
                    var_name = get_node_text(child, source_bytes)
                    if target_name is None or var_name == target_name:
                        symbols.append({
                            "name": var_name,
                            "type": "variable",
                            "line": n.start_point[0] + 1,
                            "end_line": n.end_point[0] + 1,
                        })
                    break
                elif child.type == "pattern_list":
                    # 多变量赋值 a, b = ...
                    for pattern_child in child.children:
                        if pattern_child.type == "identifier":
                            var_name = get_node_text(pattern_child, source_bytes)
                            if target_name is None or var_name == target_name:
                                symbols.append({
                                    "name": var_name,
                                    "type": "variable",
                                    "line": n.start_point[0] + 1,
                                    "end_line": n.end_point[0] + 1,
                                })
                    break
        
        elif n.type == "expression_statement":
            # 遍历 expression_statement 的子节点，查找 assignment
            for child in n.children:
                visit(child, parent_class)
        
        elif n.type in ("module", "block"):
            # 遍历子节点
            for child in n.children:
                visit(child, parent_class)
    
    visit(node)
    return symbols


@app.command()
def analyze(file_path: str):
    """
    分析文件结构，返回省略函数体和注释的代码骨架
    
    Example:
        python -m agentscope_agent.tools.tree_sitter_cli analyze program.py
    """
    path = Path(file_path)
    if not path.exists():
        print(json.dumps({"error": f"File not found: {file_path}"}))
        raise typer.Exit(1)
    
    if not path.suffix == ".py":
        print(json.dumps({"error": f"Only Python files are supported: {file_path}"}))
        raise typer.Exit(1)
    
    source_bytes = path.read_bytes()
    parser = create_parser()
    tree = parser.parse(source_bytes)
    
    skeleton_lines = extract_skeleton(tree.root_node, source_bytes)
    skeleton = "\n".join(skeleton_lines)
    
    print(skeleton)


@app.command("find-symbol")
def find_symbol(file_path: str, symbol_name: str):
    """
    查找符号定义位置（函数、类、变量等）
    
    Example:
        python -m agentscope_agent.tools.tree_sitter_cli find-symbol program.py extract_date
    """
    path = Path(file_path)
    if not path.exists():
        print(json.dumps({"error": f"File not found: {file_path}"}))
        raise typer.Exit(1)
    
    if not path.suffix == ".py":
        print(json.dumps({"error": f"Only Python files are supported: {file_path}"}))
        raise typer.Exit(1)
    
    source_bytes = path.read_bytes()
    parser = create_parser()
    tree = parser.parse(source_bytes)
    
    symbols = find_symbols(tree.root_node, source_bytes, symbol_name)
    
    if not symbols:
        print(json.dumps({"error": f"Symbol not found: {symbol_name}"}))
        raise typer.Exit(1)
    
    # 返回第一个匹配的符号（通常只有一个）
    if len(symbols) == 1:
        print(json.dumps(symbols[0], ensure_ascii=False))
    else:
        # 多个匹配时返回数组
        print(json.dumps(symbols, ensure_ascii=False))


@app.command("list-symbols")
def list_symbols(file_path: str):
    """
    列出文件中所有符号定义
    
    Example:
        python -m agentscope_agent.tools.tree_sitter_cli list-symbols program.py
    """
    path = Path(file_path)
    if not path.exists():
        print(json.dumps({"error": f"File not found: {file_path}"}))
        raise typer.Exit(1)
    
    if not path.suffix == ".py":
        print(json.dumps({"error": f"Only Python files are supported: {file_path}"}))
        raise typer.Exit(1)
    
    source_bytes = path.read_bytes()
    parser = create_parser()
    tree = parser.parse(source_bytes)
    
    symbols = find_symbols(tree.root_node, source_bytes)
    print(json.dumps(symbols, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
