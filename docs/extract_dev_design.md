# Extract Dev 模块设计

## 模块结构

```
src/extract_dev/
├── __init__.py
├── cli.py          # CLI 入口 + 所有命令实现
├── api.py          # Code API（面向对象的异步评估接口）
├── config.py       # 配置管理（环境变量 + 命令行）
├── override.py     # 覆盖层管理（.extract-dev/ 目录下的本地标注数据）
└── html_report.py  # HTML 报告生成
```

## 配置管理 (`config.py`)

### 环境变量

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `EXTRACT_SET_ID` | 标准集 ID | 无 |
| `EXTRACT_BASE_URL` | API 基础地址 | `http://localhost:8008` |
| `EXTRACT_PROGRAM` | 程序文件路径 | `./program.py` |

### 配置优先级

```
命令行参数 > 环境变量 > 默认值
```

### 配置类设计 (pydantic-settings)

```python
from pydantic_settings import BaseSettings
from pydantic import Field

class ExtractDevSettings(BaseSettings):
    """Extract Dev 配置，支持环境变量自动加载"""
    
    set_id: str = Field(default="", alias="EXTRACT_SET_ID")
    base_url: str = Field(default="http://localhost:8008", alias="EXTRACT_BASE_URL")
    program: str = Field(default="./program.py", alias="EXTRACT_PROGRAM")
    
    model_config = {
        "env_prefix": "",  # 不使用前缀，直接用 alias
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }
    
    def with_overrides(self, set_id: str | None = None, program: str | None = None) -> 'ExtractDevSettings':
        """创建带命令行覆盖的新配置"""
        return ExtractDevSettings(
            set_id=set_id or self.set_id,
            base_url=self.base_url,
            program=program or self.program,
        )
    
    def print_header(self):
        """打印配置头信息"""
        print(f"[extract-dev] set_id: {self.set_id}")
        print(f"[extract-dev] program: {self.program}")
        print(f"[extract-dev] base_url: {self.base_url}")
        print("---")
    
    def validate_required(self):
        """验证必需配置"""
        if not self.set_id:
            raise ValueError("EXTRACT_SET_ID 未设置，请设置环境变量或使用 --set-id 参数")
```

## CLI 设计 (`cli.py`)

### 命令结构

使用 Typer 实现，关闭 rich 输出（保持纯文本）：

```python
app = typer.Typer(
    help="Extract Dev - 提取程序开发工具",
    pretty_exceptions_enable=False,  # 关闭 rich 异常
    rich_markup_mode=None,           # 关闭 rich markup
)

@app.command()
def doc(doc_id: str, set_id: str = None, dataset: str = "train"): ...

@app.command()
def standard(doc_id: str, set_id: str = None, dataset: str = "train"): ...

@app.command()
def run(doc_id: str, program: str = None, set_id: str = None, dataset: str = "train"): ...

@app.command()
def train(
    program: str = None,
    set_id: str = None,
    key: list[str] = None,           # 指定评估字段
    show_correct_ids: bool = False,
    show_incorrect_ids: bool = True,
    show_details: bool = False,
): ...

@app.command()
def test(
    program: str = None,
    set_id: str = None,
    key: list[str] = None,           # 指定评估字段
    show_correct_ids: bool = False,
    show_incorrect_ids: bool = True,
    show_details: bool = False,
): ...

@app.command()
def list(set_id: str = None, dataset: str = "train"): ...

@app.command()
def schema(set_id: str = None): ...

@app.command()
def context(): ...

# --- 覆盖层命令（无标注模式） ---

@app.command()
def pseudo_init(set_id: str = None): ...

@app.command()
def set_schema(schema_json: str): ...

@app.command()
def label(doc_id: str, labels_json: str, dataset: str = "train"): ...

@app.command()
def labels(dataset: str = None): ...

@app.command()
def reset_labels(dataset: str = None): ...
```

### 命令实现依赖

| 命令 | 依赖模块 | 主要调用 |
|------|----------|----------|
| `doc` | `evaluation_engine` | `dataset.get_standard()` → `info.document.md` |
| `standard` | `evaluation_engine`, `override` | 覆盖层优先 → `get_label()` |
| `run` | `evaluation_engine`, `override` | 覆盖层存在时 `patch_engine_for_run()` |
| `train` | `evaluation_engine`, `override` | 覆盖层存在时 `patch_engine_with_override()` |
| `test` | `evaluation_engine`, `override` | 覆盖层存在时 `patch_engine_with_override(dataset="test")` |
| `list` | `api` | `list_doc_ids(dataset=...)` |
| `schema` | `evaluation_engine`, `override` | 覆盖层优先 → `get_schema()` |
| `context` | `code_executor` | `get_llm_context()` |
| `pseudo-init` | `override` | `init_override(set_id=...)` |
| `set-schema` | `override` | `set_schema(schema)` |
| `label` | `override` | `add_label(doc_id, labels, dataset=...)` |
| `labels` | `override` | `get_labels(dataset=...)` |
| `reset-labels` | `override` | `reset_labels(dataset=...)` |

## 数据缓存

使用 `.cache/` 目录缓存下载的数据集：

```python
def get_or_download_dataset(set_id: str, base_url: str) -> str:
    """获取数据集路径，如果不存在则下载"""
    cache_dir = ".cache"
    data_path = Path(cache_dir) / set_id.replace("-", "")
    
    if data_path.exists():
        return str(data_path)
    
    # 下载数据集
    return download_dataset(set_id, base_url, cache_dir, use_cache=True)
```

## 数据集访问

### 访问策略

| 命令 | 默认数据集 | `--dataset` 支持 | 覆盖层 |
|------|-----------|-----------------|--------|
| `doc` | train | train/test | 无（始终从 .cache） |
| `standard` | train | train/test | 覆盖层优先 |
| `run` | train | train/test | 覆盖层 schema + labels |
| `list` | train | train/test | 无 |
| `train` | train | — | 覆盖层 schema + labels，只评估已标注文档 |
| `test` | test | — | 覆盖层 schema |
| `schema` | — | — | 覆盖层优先 |

### 覆盖层机制

覆盖层目录 `workspace/.extract-dev/` 存储本地标注数据，优先级高于 `.cache` 中的标准集：

```
workspace/.extract-dev/
├── schema.json       # 本地 schema（extract-dev set-schema 写入）
└── labels.json       # 本地标注（extract-dev label 写入，支持 train/test dataset 字段）
```

**优先级规则**：
- `schema` → 覆盖层 schema 优先，覆盖层已初始化但无 schema 时报错（不 fallback）
- `standard` → 覆盖层 labels 优先，覆盖层已初始化但未标注时报错（不 fallback）
- `train` → 覆盖层存在时，替换 schema + labels，只评估已标注文档
- `test` → 覆盖层存在时，替换 schema，已标注文档用覆盖层 labels，未标注文档过滤字段
- `doc` → 始终从 `.cache`（文档本身不覆盖）

### train/test 命令输出

```python
def _print_evaluation_report(
    title: str,
    evaluation_result,
    keys: list[str] | None = None,
    show_correct_ids: bool = False,
    show_incorrect_ids: bool = True,
    show_details: bool = False,
):
    """Markdown 格式输出"""
    print(f"# {title}评估报告\n")
    print(f"- **总体准确率**: {evaluation_result.overall_accuracy:.2%}")
    print(f"- **字段平均准确率**: {field_average:.2%}")
    # ...字段统计表格、文档 ID 列表、详细对比
```

## context 命令输出

```python
def context_command():
    from code_executor import get_structure_code
    from code_executor.tools import has_default_tool, create_default_llm_guide
    
    output = []
    
    # 1. 代码入口签名
    output.append("## 代码入口签名")
    output.append("""
```python
def extract(article: list[str|Table]) -> dict[str, Any]:
    ...
```
""")
    
    # 2. structure.py 内容
    output.append("## code_executor/structure.py")
    output.append(f"```python\n{get_structure_code()}\n```")
    
    # 3. 工具指南（如果有）
    if has_default_tool():
        output.append("## 工具指南")
        output.append(create_default_llm_guide())
    
    print("\n".join(output))
```

## CLI 注册

```toml
# pyproject.toml
[project.scripts]
extract-dev = "extract_dev.cli:app"
```

## 错误处理

- 环境变量未设置 → 提示用户设置
- 文档 ID 不存在 → 明确错误信息
- 程序文件不存在 → 明确错误信息
- 网络错误 → 重试或提示
