"""
并发标注 Workflow

提供 create_label_all_documents_tool 工厂函数，
创建 label_all_documents 工具供 BusinessAgent 调用。
"""

import asyncio
import json
import logging
from pathlib import Path

from agentscope.tool import ToolResponse
from agentscope.message import TextBlock

from .agent import LabelingAgent

logger = logging.getLogger(__name__)


_MAX_CONCURRENT = 16


def create_label_all_documents_tool(
    labeling_model: str,
    labeling_api_base: str,
    labeling_api_key: str,
    labeling_timeout: float = 300.0,
    labeling_max_retries: int = 0,
    data_dir: str | None = None,
):
    """创建 label_all_documents 工具函数

    Args:
        labeling_model: 标注 agent 模型
        labeling_api_base: 标注 agent API 地址
        labeling_api_key: 标注 agent API Key
        labeling_timeout: 标注 agent API 超时
        labeling_max_retries: 标注 agent 最大重试次数
        data_dir: xdev 数据目录（默认 .xdev）
    """

    async def label_all_documents(
        doc_ids: str = "",
        relabel_mismatched: bool = False,
    ) -> ToolResponse:
        """批量标注文档。为每个文档启动独立的标注 Agent 并发执行。

        默认标注所有未标注的文档。

        Args:
            doc_ids: 逗号分隔的文档 ID（可选，为空则标注全部未标注文档）
            relabel_mismatched: 是否同时重新标注与 schema 不匹配的文档

        Returns:
            ToolResponse 包含标注结果摘要
        """
        from xdev.api import get_schema, list_doc_ids, get_docjson_path, get_label_path

        # 1. 检查 schema
        schema = get_schema(data_dir)
        if schema is None:
            return ToolResponse(
                content=[TextBlock(
                    type="text",
                    text="错误：请先创建 .xdev/schema.json 定义 schema",
                )]
            )

        schema_json = json.dumps(schema.model_dump(), ensure_ascii=False, indent=2)

        # 2. 读取 business_guide
        guide_path = Path("business_guide.md")
        if guide_path.exists():
            business_guide = guide_path.read_text(encoding="utf-8")
        else:
            business_guide = "（无业务指导文档）"

        # 3. 确定要标注的文档列表
        all_ids = list_doc_ids(data_dir)

        if doc_ids.strip():
            target_ids = [d.strip() for d in doc_ids.split(",") if d.strip()]
            valid_ids = set(all_ids)
            target_ids = [d for d in target_ids if d in valid_ids]
        else:
            # 标注所有未标注的文档
            target_ids = []
            for did in all_ids:
                label_path = get_label_path(did, data_dir)
                if not label_path.exists():
                    target_ids.append(did)

        # 3.1 如果需要，加入 schema 不匹配的文档
        if relabel_mismatched:
            from xdev.api import check_label_status
            try:
                status = check_label_status(data_dir)
                existing = set(target_ids)
                for mid in status.mismatched_ids:
                    if mid not in existing:
                        target_ids.append(mid)
                        existing.add(mid)
                if status.mismatched_ids:
                    logger.info("加入 %d 篇 schema 不匹配文档重新标注", len(status.mismatched_ids))
            except FileNotFoundError:
                pass

        if not target_ids:
            return ToolResponse(
                content=[TextBlock(type="text", text="没有需要标注的文档（所有文档已标注）")]
            )

        total = len(target_ids)
        logger.info("开始并发标注 %d 篇文档（并发度: %d）", total, _MAX_CONCURRENT)

        # 4. 并发执行标注
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
        results: dict[str, bool] = {}

        async def _label_one(doc_id: str):
            async with semaphore:
                docjson_path = str(get_docjson_path(doc_id, data_dir))
                agent = LabelingAgent(
                    model=labeling_model,
                    api_base=labeling_api_base,
                    api_key=labeling_api_key,
                    timeout=labeling_timeout,
                    max_retries=labeling_max_retries,
                )
                success = await agent.label_document(
                    doc_id=doc_id,
                    schema_json=schema_json,
                    business_guide=business_guide,
                    docjson_path=docjson_path,
                )
                results[doc_id] = success
                done = len(results)
                if done % 5 == 0 or done == total:
                    logger.info("标注进度: %d/%d", done, total)

        await asyncio.gather(*[_label_one(did) for did in target_ids])

        # 5. 汇总结果
        success_count = sum(1 for ok in results.values() if ok)
        failed_ids = [did for did, ok in results.items() if not ok]

        lines = [
            "标注完成。",
            f"总计: {total} 篇文档",
            f"成功: {success_count} 篇",
            f"失败: {len(failed_ids)} 篇",
        ]
        if failed_ids:
            lines.append(f"失败文档: {', '.join(failed_ids)}")

        summary = "\n".join(lines)
        logger.info(summary)

        return ToolResponse(
            content=[TextBlock(type="text", text=summary)]
        )

    return label_all_documents
