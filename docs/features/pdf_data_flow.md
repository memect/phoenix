# PDF 数据流

本文档说明 PDF 原始数据如何从下载到最终在 `extract()` 函数中使用的完整流程。

> **完整方案**：参见 [VLM 提取方案](./vlm_extract_solution.md)

## 概述

为支持 VLM 工具从 PDF 原始图像中提取信息，系统需要将 PDF 二进制数据传递到 `extract()` 函数中的 `Document.raw_bytes` 属性。

## 数据流路径

```
┌─────────────────────────────────────────────────────────────────┐
│  1. ResourceGenerator.download_resources(download_pdf=True)     │
│     下载 PDF 文件到本地缓存                                       │
│     位置：evaluator/standards/dataset_app.py                     │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. 本地缓存：pdf/{hex_id}.pdf                                   │
│     标准集目录下的 pdf/ 子目录                                    │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. DirectoryStandardSetLoader._load_document_for_standard()    │
│     加载标准集时设置 document.pdf_path                           │
│     位置：evaluator/standards/loader/direcotry_loader.py        │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. evaluator.Document.get_pdf_bytes()                          │
│     根据 pdf_path 读取 PDF 二进制数据                            │
│     位置：evaluator/core/evaluation_models.py                   │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. EvaluationEngine._extract_from_document()                   │
│     调用 get_pdf_bytes() 并传给 create_input()                  │
│     位置：evaluation_engine/engine.py                           │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. code_executor.create_input(docjson, pdf_bytes=...)          │
│     设置 doc.raw_bytes = pdf_bytes                              │
│     位置：code_executor/executor.py                             │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  7. extract(document: Document)                                 │
│     用户代码中通过 document.raw_bytes 访问 PDF 数据              │
└─────────────────────────────────────────────────────────────────┘
```

## 各模块实现

### 1. ResourceGenerator - PDF 下载

`evaluator/standards/dataset_app.py`:

```python
class ResourceGenerator:
    def download_resources(self, download_pdf: bool = False):
        """下载资源文件"""
        if download_pdf:
            self._download_pdfs()
    
    def _download_pdfs(self):
        """下载 PDF 文件到 pdf/ 目录"""
        pdf_dir = self.output_dir / "pdf"
        pdf_dir.mkdir(exist_ok=True)
        
        for item in self.items:
            hex_id = item.hex_id
            pdf_path = pdf_dir / f"{hex_id}.pdf"
            if not pdf_path.exists():
                # 从 API 下载 PDF
                pdf_bytes = self._fetch_pdf(item.document_id)
                pdf_path.write_bytes(pdf_bytes)
```

### 2. evaluator.Document - PDF 路径和读取

`evaluator/core/evaluation_models.py`:

```python
class Document(BaseModel):
    """文档模型"""
    pdf_path: Path | None = None  # PDF 文件路径
    
    def get_pdf_bytes(self) -> bytes | None:
        """获取 PDF 二进制数据"""
        if self.pdf_path and self.pdf_path.exists():
            return self.pdf_path.read_bytes()
        return None
```

### 3. DirectoryStandardSetLoader - 加载时设置 pdf_path

`evaluator/standards/loader/direcotry_loader.py`:

```python
def _load_document_for_standard(self, std: Standard) -> Document:
    """加载标准集对应的文档"""
    document = Document(...)
    
    # 设置 PDF 路径
    pdf_path = self.data_path / "pdf" / f"{std.hex_id}.pdf"
    if pdf_path.exists():
        document.pdf_path = pdf_path
    
    return document
```

### 4. EvaluationEngine - 传递 PDF 数据

`evaluation_engine/engine.py`:

```python
async def _extract_from_document(self, program: str, document: Document) -> dict:
    """从文档中提取数据"""
    # 获取 PDF 字节
    pdf_bytes = document.get_pdf_bytes()
    
    # 创建输入
    input_data = create_input(document.docjson, pdf_bytes=pdf_bytes)
    
    # 执行提取
    return execute(program, input_data)
```

### 5. code_executor.create_input - 设置 raw_bytes

`code_executor/executor.py`:

```python
def create_input(
    docjson: dict,
    mode: str | None = None,
    pdf_bytes: bytes | None = None,
) -> Document | list:
    """创建提取函数的输入"""
    doc = Document(...)
    
    # 设置 PDF 原始数据
    if pdf_bytes:
        doc.raw_bytes = pdf_bytes
    
    return doc
```

### 6. code_executor.Document.raw_bytes

`code_executor/document/models/document.py`:

```python
class Document(BaseModel):
    """文档模型（用于 extract 函数）"""
    raw_bytes: bytes | None = None  # 原始 PDF 二进制数据
```

## 使用示例

在 `program.py` 中访问 PDF 数据：

```python
from code_executor import Document
from code_executor.tools import ToolHub
from pydantic import BaseModel

def extract(document: Document, tool_hub: ToolHub) -> dict:
    # 检查是否有 PDF 原始数据
    if document.raw_bytes:
                pdf_tool = tool_hub.get_tool('pdf_to_image')
        vlm_tool = tool_hub.get_tool('vlm_extract')
        
        # 将 PDF 转为图片
        images = pdf_tool(document.raw_bytes, pages=1)
        
        # 使用 VLM 提取
        class MySchema(BaseModel):
            title: str | None
            content: str | None
        
        return vlm_tool(images, schema=MySchema)
    
    # 无 PDF 数据时使用常规提取
    return {"title": document.title, ...}
```

## 相关文件

| 文件 | 功能 |
|------|------|
| `evaluator/standards/dataset_app.py` | ResourceGenerator，PDF 下载 |
| `evaluator/core/evaluation_models.py` | evaluator.Document，pdf_path 和 get_pdf_bytes |
| `evaluator/standards/loader/direcotry_loader.py` | 加载时设置 pdf_path |
| `evaluation_engine/engine.py` | 传递 pdf_bytes 到 create_input |
| `code_executor/executor.py` | create_input 接收 pdf_bytes |
| `code_executor/document/models/document.py` | code_executor.Document.raw_bytes |
