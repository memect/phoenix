# Tree-sitter CLI 使用指南

Tree-sitter CLI 是一个基于 tree-sitter 的代码结构分析工具，帮助快速理解 Python 代码组织。

## 安装

Tree-sitter CLI 依赖以下包：

```bash
pip install tree-sitter tree-sitter-python typer
```

或通过项目依赖安装：

```bash
uv sync
```

## 命令

### analyze - 分析文件结构

返回省略函数体和注释的代码骨架，快速了解文件结构。

```bash
tree-sitter-cli analyze <file.py>
```

**示例**：

输入文件 `program.py`：
```python
"""提取程序"""
import re
from typing import Optional

class MyExtractor:
    """提取器类"""
    
    def __init__(self, config: dict):
        self.config = config
    
    def extract_date(self, text: str) -> Optional[str]:
        """提取日期"""
        pattern = r'\d{4}-\d{2}-\d{2}'
        match = re.search(pattern, text)
        return match.group() if match else None

def main():
    extractor = MyExtractor({})
    result = extractor.extract_date("2024-01-15")
    print(result)

if __name__ == "__main__":
    main()
```

输出：
```
import re
from typing import Optional

class MyExtractor :
    def __init__(self, config: dict): ...
    def extract_date(self, text: str) -> Optional[str]: ...

def main(): ...

if __name__ == "__main__": ...
```

### find-symbol - 查找符号定义

查找函数、类、变量等符号的定义位置。

```bash
tree-sitter-cli find-symbol <file.py> <symbol_name>
```

**示例**：

```bash
tree-sitter-cli find-symbol program.py extract_date
```

输出（JSON 格式）：
```json
{"name": "MyExtractor.extract_date", "type": "method", "line": 11, "end_line": 15}
```

**支持的符号类型**：
- `class` - 类定义
- `function` - 函数定义
- `method` - 类方法
- `variable` - 变量赋值

### list-symbols - 列出所有符号

列出文件中所有符号定义。

```bash
tree-sitter-cli list-symbols <file.py>
```

**示例**：

```bash
tree-sitter-cli list-symbols program.py
```

输出（JSON 数组）：
```json
[
  {"name": "MyExtractor", "type": "class", "line": 5, "end_line": 15},
  {"name": "MyExtractor.__init__", "type": "method", "line": 8, "end_line": 9},
  {"name": "MyExtractor.extract_date", "type": "method", "line": 11, "end_line": 15},
  {"name": "main", "type": "function", "line": 17, "end_line": 20}
]
```

## 使用场景

### 1. 快速了解文件结构

在修改代码前，先了解文件的整体结构：

```bash
tree-sitter-cli analyze program.py
```

### 2. 定位特定函数

查找要修改的函数的位置：

```bash
tree-sitter-cli find-symbol program.py extract_date
```

然后用 `view_text_file` 查看具体行：

```bash
# 假设返回 line: 11, end_line: 15
view_text_file program.py --start 11 --end 15
```

### 3. 查看所有定义

了解文件中有哪些函数和类：

```bash
tree-sitter-cli list-symbols program.py
```

## 限制

- 仅支持 Python 文件 (.py)
- 不支持动态生成的代码
- 不解析 `exec()` 或 `eval()` 中的代码

## 错误处理

**文件不存在**：
```json
{"error": "File not found: program.py"}
```

**非 Python 文件**：
```json
{"error": "Only Python files are supported: data.json"}
```

**符号未找到**：
```json
{"error": "Symbol not found: nonexistent_function"}
```
