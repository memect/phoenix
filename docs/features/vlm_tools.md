# VLM 工具集

本文档介绍 VLM（视觉语言模型）相关工具的 API 和配置。

> **完整方案**：参见 [VLM 提取方案](./vlm_extract_solution.md)

## VLMExtractTool - 图片信息提取

### 概述
基于视觉语言模型的图片信息提取工具，支持从图片中提取结构化数据。

### 功能特性
- **多种输入格式**：URL、base64、本地文件路径、bytes 二进制数据
- **多图支持**：支持单张或多张图片，多图时一起分析提取一份结构化数据
- **结构化输出**：通过 pydantic schema 定义输出结构
- **MIME 类型自动检测**：通过 magic number 自动识别图片格式
- **大小限制**：可配置的图片大小限制（默认 20MB）

### 使用方式

#### 1. 直接实例化
```python
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from code_executor.tools import VLMExtractTool

# 创建 VLM 客户端
llm = ChatOpenAI(
    model="gemini-2.5-flash-nothinking",
    api_key="your-api-key",
    base_url="https://api.example.com/v1",
)

# 创建工具
tool = VLMExtractTool(llm=llm, max_image_size=20*1024*1024)

# 定义 schema
class DocumentInfo(BaseModel):
    title: str | None = Field(description="文档标题")
    date: str | None = Field(description="日期")

# 单张图片提取
result = tool(images="/path/to/image.png", schema=DocumentInfo)

# 多张图片提取（如多页文档）
result = tool(images=["/page1.png", "/page2.png"], schema=DocumentInfo)
```

#### 2. 通过 ToolHub（推荐）
```python
vlm_tool = tool_hub.get_tool('vlm_extract')

result = vlm_tool(images="/path/to/image.png", schema=MySchema)
```

### 输入格式

| 类型 | 示例 | 说明 |
|------|------|------|
| URL | `https://example.com/image.png` | 以 http/https 开头 |
| base64 | `data:image/png;base64,xxx...` | 以 data:image/ 开头 |
| 本地路径 | `/path/to/image.png` | 自动读取并转 base64 |
| bytes | `b'\x89PNG...'` | 二进制数据，自动转 base64 |

### 配置参数

#### 构造参数
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| llm | BaseChatModel | 必填 | 支持视觉的语言模型 |
| max_image_size | int | 20MB | 单张图片最大大小（字节） |

#### 环境变量（`.code_tools.env`）
```env
CODET_TOOL_SETUP__VLM_EXTRACT_TOOL__LLM__TYPE=openai
CODET_TOOL_SETUP__VLM_EXTRACT_TOOL__LLM__CONFIG__API_KEY=your-api-key
CODET_TOOL_SETUP__VLM_EXTRACT_TOOL__LLM__CONFIG__API_BASE=https://api.example.com/v1
CODET_TOOL_SETUP__VLM_EXTRACT_TOOL__LLM__CONFIG__MODEL=gemini-2.5-flash-nothinking
CODET_TOOL_SETUP__VLM_EXTRACT_TOOL__MAX_IMAGE_SIZE=20971520  # 可选
```

### 支持的 VLM 模型
已测试可用：
- `gpt-4o`
- `gemini-2.0-flash`
- `gemini-2.5-flash-nothinking`
- `claude-3-5-sonnet-20241022`

---

## PDFToImageTool - PDF 转图片

### 概述
将 PDF 的指定页面转换为 PNG 图片，通常配合 VLMExtractTool 使用。

### 功能特性
- 支持从 PDF bytes 转换指定页面为 PNG 图片
- 支持单页或多页转换
- 可配置 DPI（默认 150）
- 返回 base64 编码的图片列表

### 使用方式

```python
pdf_tool = tool_hub.get_tool('pdf_to_image')

# 获取第 1 页的图片（返回 base64 编码的 PNG）
images = pdf_tool(pdf_bytes, pages=1)

# 获取多页
images = pdf_tool(pdf_bytes, pages=[1, 2, 3])

# 获取全部页面
images = pdf_tool(pdf_bytes, pages=None)
```

### 配置

环境变量（`.code_tools.env`）：
```env
CODET_TOOL_SETUP__PDF_TO_IMAGE_TOOL__DPI=200  # 可选，默认 150
```

### 依赖
- `pymupdf>=1.24.0`

---

## 文件结构
```
src/code_executor/tools/
├── tool_defines/
│   ├── vlm_extract_tool.py    # VLMExtractTool 实现
│   └── pdf_to_image_tool.py   # PDFToImageTool 实现
├── tool_setup/
│   ├── settings.py            # 工具配置类
│   └── load.py                # 工具加载逻辑
└── __init__.py                # 导出
```
