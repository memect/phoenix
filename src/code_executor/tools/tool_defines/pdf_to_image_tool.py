"""
PDF 转图片工具

使用 PyMuPDF 将 PDF 指定页面转换为 PNG 图片。
"""

from typing import Annotated

from code_executor.tools.tool_center import tool


@tool(name='pdf_to_image', methods=['__call__'], description='PDF 转图片工具')
class PDFToImageTool:
    """PDF 转图片工具 - 将 PDF 指定页面转换为 PNG 图片
    
    支持从 PDF 二进制数据中提取指定页面并转换为 PNG 图片。
    页码从 1 开始，与 Document API 保持一致。
    
    示例：
        ```python
        # tool_hub 由 xdev 注入到 extract(document, tool_hub)
        pdf_tool = tool_hub.get_tool('pdf_to_image')
        
        # 获取第 1 页
        images = pdf_tool(pdf_bytes, pages=1)
        
        # 获取多页
        images = pdf_tool(pdf_bytes, pages=[1, 2, 3])
        
        # 配合 vlm_extract 使用
        vlm_tool = tool_hub.get_tool('vlm_extract')
        result = vlm_tool(images, schema=MySchema)
        ```
    """
    
    def __init__(self, dpi: int = 150):
        """初始化 PDF 转图片工具。
        
        Args:
            dpi: 输出图片的分辨率，默认 150 DPI
        """
        self.dpi = dpi

    def __call__(
        self,
        pdf_bytes: Annotated[bytes, 'PDF 文件的二进制数据'],
        pages: Annotated[int | list[int], '要转换的页码，从 1 开始。可以是单个页码或页码列表'],
    ) -> list[bytes]:
        """将 PDF 指定页面转换为 PNG 图片。
        
        Args:
            pdf_bytes: PDF 文件的二进制数据
            pages: 要转换的页码（从 1 开始）。可以是：
                - 单个页码：如 1, 2, 3
                - 页码列表：如 [1, 2, 3]
        
        Returns:
            PNG 图片的 bytes 列表，顺序与输入页码一致
        
        Raises:
            ValueError: 页码无效（小于 1 或超出 PDF 总页数）
            RuntimeError: PDF 解析失败
        """
        import fitz  # PyMuPDF
        
        # 统一转成列表
        if isinstance(pages, int):
            pages = [pages]
        
        if not pages:
            raise ValueError("至少需要指定一个页码")
        
        # 验证页码
        for page_num in pages:
            if page_num < 1:
                raise ValueError(f"页码必须从 1 开始，收到: {page_num}")
        
        try:
            # 从 bytes 打开 PDF
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise RuntimeError(f"PDF 解析失败: {e}") from e
        
        try:
            total_pages = len(doc)
            
            # 验证页码范围
            for page_num in pages:
                if page_num > total_pages:
                    raise ValueError(
                        f"页码 {page_num} 超出 PDF 总页数 {total_pages}"
                    )
            
            # 计算缩放比例（基于 DPI）
            # PyMuPDF 默认 72 DPI
            zoom = self.dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)
            
            # 转换每一页
            result = []
            for page_num in pages:
                # PyMuPDF 页码从 0 开始，需要减 1
                page = doc[page_num - 1]
                
                # 渲染为图片
                pix = page.get_pixmap(matrix=matrix)
                
                # 转换为 PNG bytes
                png_bytes = pix.tobytes("png")
                result.append(png_bytes)
            
            return result
        finally:
            doc.close()
