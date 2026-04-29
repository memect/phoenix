# VLM 提取方案

本文档是 VLM（视觉语言模型）提取方案的入口文档，串联各部分实现。

## 背景

### 问题

部分文档存在以下情况，传统的文本解析无法有效提取信息：
- 扫描件/图片型 PDF，文字无法直接提取
- 表格以图片形式存在，结构化解析失败
- 文档解析质量差，但原始 PDF 可读

### 解决方案

使用 VLM（视觉语言模型）从 PDF 原始图像中直接提取结构化信息。

## 整体逻辑链条

```
┌─────────────────────────────────────────────────────────────────────┐
│                          VLM 提取方案                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │   工具配置   │───▶│  工具上下文  │───▶│  策略提示词  │             │
│  │.code_tools │    │extract-dev │    │ STRATEGIES │             │
│  │   .env     │    │  context   │    │            │             │
│  └─────────────┘    └─────────────┘    └─────────────┘             │
│         │                 │                  │                     │
│         ▼                 ▼                  ▼                     │
│  ┌─────────────────────────────────────────────────┐               │
│  │              Agent 系统提示词                    │               │
│  │   - 知道有哪些工具可用（LLM Guide）             │               │
│  │   - 知道何时使用 VLM 提取（STRATEGIES）         │               │
│  └─────────────────────────────────────────────────┘               │
│                           │                                        │
│                           ▼                                        │
│  ┌─────────────────────────────────────────────────┐               │
│  │              Agent 编写 program.py              │               │
│  │   - 使用 document.raw_bytes 获取 PDF 数据       │               │
│  │   - 使用 pdf_to_image 转换为图片                │               │
│  │   - 使用 vlm_extract 提取结构化数据             │               │
│  └─────────────────────────────────────────────────┘               │
│                           │                                        │
│                           ▼                                        │
│  ┌─────────────────────────────────────────────────┐               │
│  │              运行时数据流                        │               │
│  │   PDF 下载 → pdf_path → get_pdf_bytes()        │               │
│  │   → create_input(pdf_bytes) → doc.raw_bytes    │               │
│  └─────────────────────────────────────────────────┘               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 快速上手

### 1. 配置工具

创建 `.code_tools.env`（项目根目录）：

```env
# VLM 图片提取工具
CODET_TOOL_SETUP__VLM_EXTRACT_TOOL__LLM__TYPE=openai
CODET_TOOL_SETUP__VLM_EXTRACT_TOOL__LLM__CONFIG__API_KEY=your-api-key
CODET_TOOL_SETUP__VLM_EXTRACT_TOOL__LLM__CONFIG__API_BASE=https://api.example.com/v1
CODET_TOOL_SETUP__VLM_EXTRACT_TOOL__LLM__CONFIG__MODEL=gemini-2.5-flash-nothinking

# PDF 转图片工具（可选配置 DPI）
CODET_TOOL_SETUP__PDF_TO_IMAGE_TOOL__DPI=150
```

### 2. 下载 PDF 数据

确保标准集包含 PDF 文件：

```bash
# 运行 agentscope-agent 时会自动下载 PDF（如果配置了 download_pdf）
uv run agentscope-agent run --set-id xxx
```

### 3. 验证工具上下文

```bash
# 检查工具是否正确加载
uv run extract-dev context

# 输出应包含 "可用工具" 部分
```

### 4. 编写提取代码

在 `program.py` 中使用 VLM 工具：

```python
from code_executor import Document
from code_executor.tools import ToolHub
from pydantic import BaseModel

def extract(document: Document, tool_hub: ToolHub) -> dict:
    # 检查是否有 PDF 原始数据
    if document.raw_bytes:
                pdf_tool = tool_hub.get_tool('pdf_to_image')
        vlm_tool = tool_hub.get_tool('vlm_extract')
        
        # 将 PDF 第 1 页转为图片
        images = pdf_tool(document.raw_bytes, pages=1)
        
        # 定义提取结构
        class MySchema(BaseModel):
            title: str | None
            date: str | None
            content: str | None
        
        # 从图片中提取结构化数据
        return vlm_tool(images, schema=MySchema)
    
    # 无 PDF 数据时使用常规提取
    return {
        "title": document.title,
        "date": None,
        "content": document.text,
    }
```

## 详细文档

| 文档 | 内容 |
|------|------|
| [VLM 工具集](./vlm_tools.md) | VLMExtractTool、PDFToImageTool 的 API 和配置 |
| [PDF 数据流](./pdf_data_flow.md) | PDF 数据从下载到 extract 函数的完整流程 |
| [策略提示词设计](./tool_strategies.md) | STRATEGIES 设计原则、与 LLM Guide 的区别 |
| [代码工具上下文](./code_tools_context.md) | .code_tools.env → ToolHub → Agent 提示词 |

## 涉及模块

```
src/
├── code_executor/
│   ├── tools/
│   │   ├── tool_defines/
│   │   │   ├── vlm_extract_tool.py   # VLMExtractTool
│   │   │   └── pdf_to_image_tool.py  # PDFToImageTool
│   │   └── tool_setup/
│   │       ├── settings.py           # 工具配置类
│   │       └── load.py               # 工具加载
│   ├── document/models/document.py   # Document.raw_bytes
│   ├── executor.py                   # create_input(pdf_bytes)
│   └── get_tools.py                  # create_default_llm_guide()
├── evaluator/
│   ├── core/evaluation_models.py     # Document.pdf_path, get_pdf_bytes()
│   └── standards/
│       ├── dataset_app.py            # ResourceGenerator（PDF 下载）
│       └── loader/direcotry_loader.py # 加载时设置 pdf_path
├── evaluation_engine/
│   └── engine.py                     # 传递 pdf_bytes
├── agentscope_agent/
│   ├── prompts/strategies.py         # STRATEGIES 策略提示词
│   └── workflow.py                   # _load_code_tools_env()
└── extract_dev/
    └── cli.py                        # context 命令
```

## 依赖

- `pymupdf>=1.24.0` - PDF 转图片
- VLM API（如 OpenAI GPT-4o、Google Gemini 等）
