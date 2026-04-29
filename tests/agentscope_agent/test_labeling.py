"""
LabelingAgent 及并发标注工具测试
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _tool_text(result) -> str:
    block = result.content[0]
    return getattr(block, "text", block["text"])


def _write_schema(workspace, schema: dict | None = None) -> None:
    from xdev.config import ensure_data_dir

    data_dir = ensure_data_dir(".xdev")
    schema_payload = schema or {
        "type": "object",
        "data": {"title": "str", "amount": "float"},
    }
    (data_dir / "schema.json").write_text(
        json.dumps(schema_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_docjson(doc_id: str) -> None:
    from xdev.config import ensure_data_dir

    data_dir = ensure_data_dir(".xdev")
    (data_dir / "data" / "docjson" / f"{doc_id}.json").write_text(
        "{}",
        encoding="utf-8",
    )


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """创建临时工作目录并 chdir"""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def initialized_workspace(workspace):
    """已初始化 .xdev + schema 的工作目录"""
    _write_schema(workspace)
    return workspace


class TestLabelingPrompts:
    """labeling prompts 测试"""

    def test_system_prompt_not_empty(self):
        from agentic_extract.labeling.prompts import SYSTEM_PROMPT

        assert len(SYSTEM_PROMPT) > 0
        assert "xdev doc" in SYSTEM_PROMPT

    def test_build_label_message_contains_doc_id(self):
        from agentic_extract.labeling.prompts import build_label_message

        msg = build_label_message(
            doc_id="doc-001",
            schema_json='{"type": "object"}',
            business_guide="测试指导",
            docjson_path="/tmp/doc-001.json",
        )
        assert "doc-001" in msg
        assert "/tmp/doc-001.json" in msg

    def test_build_label_message_contains_schema(self):
        from agentic_extract.labeling.prompts import build_label_message

        schema = '{"type": "object", "data": {"title": "str"}}'
        msg = build_label_message(
            doc_id="doc-002",
            schema_json=schema,
            business_guide="guide",
            docjson_path="/tmp/doc-002.json",
        )
        assert schema in msg

    def test_build_label_message_contains_guide(self):
        from agentic_extract.labeling.prompts import build_label_message

        guide = "这是业务指导内容，包含提取规则"
        msg = build_label_message(
            doc_id="doc-003",
            schema_json="{}",
            business_guide=guide,
            docjson_path="/tmp/doc-003.json",
        )
        assert guide in msg

    def test_build_label_message_object_format_hint(self):
        from agentic_extract.labeling.prompts import build_label_message

        msg = build_label_message(
            doc_id="doc-005",
            schema_json='{"type": "object", "data": {"title": "str"}}',
            business_guide="guide",
            docjson_path="/tmp/doc-005.json",
        )
        assert "schema type 为 `object`" in msg
        assert '{"字段1": "值1"' in msg

    def test_build_label_message_list_of_objects_format_hint(self):
        from agentic_extract.labeling.prompts import build_label_message

        msg = build_label_message(
            doc_id="doc-006",
            schema_json='{"type": "list_of_objects", "data": {"name": "str"}}',
            business_guide="guide",
            docjson_path="/tmp/doc-006.json",
        )
        assert "schema type 为 `list_of_objects`" in msg
        assert "数组" in msg


class TestLabelingAgent:
    """LabelingAgent 单元测试（mock LLM 调用）"""

    def test_init_stores_config(self):
        from agentic_extract.labeling.agent import LabelingAgent

        agent = LabelingAgent(
            model="deepseek/deepseek-v4-flash",
            api_base="https://api.deepseek.com/v1",
            api_key="sk-test",
            timeout=120.0,
            max_retries=2,
        )
        assert agent._model == "deepseek/deepseek-v4-flash"
        assert agent._api_base == "https://api.deepseek.com/v1"
        assert agent._api_key == "sk-test"
        assert agent._timeout == 120.0
        assert agent._max_retries == 2

    @pytest.mark.asyncio
    async def test_label_document_success(self):
        """label_document 成功时返回 True"""
        from agentic_extract.labeling.agent import LabelingAgent

        mock_llm = MagicMock()
        mock_formatter = MagicMock()
        mock_react_agent_instance = AsyncMock()

        with patch(
            "agentic_extract.model_factory.create_model",
            return_value=(mock_llm, mock_formatter),
        ), patch(
            "agentic_extract.tools.register_file_tools",
            return_value=None,
        ), patch(
            "agentic_extract.labeling.agent.ReActAgent",
            return_value=mock_react_agent_instance,
        ):
            agent = LabelingAgent(
                model="test-model",
                api_base="http://localhost",
                api_key="sk-test",
            )
            result = await agent.label_document(
                doc_id="doc-001",
                schema_json='{"type": "object"}',
                business_guide="guide",
                docjson_path="/tmp/doc-001.json",
            )
            assert result is True
            mock_react_agent_instance.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_label_document_failure(self):
        """label_document 异常时返回 False"""
        from agentic_extract.labeling.agent import LabelingAgent

        mock_llm = MagicMock()
        mock_formatter = MagicMock()
        mock_react_agent_instance = AsyncMock(side_effect=RuntimeError("LLM error"))

        with patch(
            "agentic_extract.model_factory.create_model",
            return_value=(mock_llm, mock_formatter),
        ), patch(
            "agentic_extract.tools.register_file_tools",
            return_value=None,
        ), patch(
            "agentic_extract.labeling.agent.ReActAgent",
            return_value=mock_react_agent_instance,
        ):
            agent = LabelingAgent(
                model="test-model",
                api_base="http://localhost",
                api_key="sk-test",
            )
            result = await agent.label_document(
                doc_id="doc-fail",
                schema_json="{}",
                business_guide="guide",
                docjson_path="/tmp/doc-fail.json",
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_label_document_creates_independent_agent(self):
        """每次调用 label_document 都创建新的 ReActAgent 实例"""
        from agentic_extract.labeling.agent import LabelingAgent

        mock_llm = MagicMock()
        mock_formatter = MagicMock()
        call_count = 0

        def make_agent(**kwargs):
            nonlocal call_count
            call_count += 1
            return AsyncMock()

        with patch(
            "agentic_extract.model_factory.create_model",
            return_value=(mock_llm, mock_formatter),
        ), patch(
            "agentic_extract.tools.register_file_tools",
            return_value=None,
        ), patch(
            "agentic_extract.labeling.agent.ReActAgent",
            side_effect=make_agent,
        ):
            agent = LabelingAgent(
                model="test-model",
                api_base="http://localhost",
                api_key="sk-test",
            )
            await agent.label_document("d1", "{}", "g", "/tmp/d1.json")
            await agent.label_document("d2", "{}", "g", "/tmp/d2.json")
            assert call_count == 2


class TestLabelAllDocumentsTool:
    """create_label_all_documents_tool 测试"""

    def _create_tool(self):
        from agentic_extract.labeling.workflow import create_label_all_documents_tool

        return create_label_all_documents_tool(
            labeling_model="test-model",
            labeling_api_base="http://localhost",
            labeling_api_key="sk-test",
        )

    def test_create_tool_returns_callable(self):
        tool = self._create_tool()
        assert callable(tool)
        assert tool.__name__ == "label_all_documents"

    def test_tool_has_docstring(self):
        tool = self._create_tool()
        assert tool.__doc__ is not None
        assert "批量标注" in tool.__doc__

    @pytest.mark.asyncio
    async def test_no_schema_returns_error(self, workspace):
        """没有 schema 时返回错误"""
        from xdev.config import ensure_data_dir

        ensure_data_dir(".xdev")
        tool = self._create_tool()
        result = await tool()
        text = _tool_text(result)
        assert "schema" in text.lower()

    @pytest.mark.asyncio
    async def test_no_documents_returns_empty(self, initialized_workspace):
        """没有文档时返回空提示"""
        tool = self._create_tool()
        result = await tool()
        text = _tool_text(result)
        assert "没有需要标注的文档" in text

    @pytest.mark.asyncio
    async def test_label_all_documents_success(self, initialized_workspace):
        """全量标注成功"""
        (initialized_workspace / "business_guide.md").write_text("测试指导", encoding="utf-8")
        for doc_id in ("t1", "t2", "e1"):
            _write_docjson(doc_id)

        tool = self._create_tool()
        labeled = []

        def make_mock_agent(**kwargs):
            inst = MagicMock()

            async def label_doc(doc_id, schema_json, business_guide, docjson_path):
                labeled.append((doc_id, business_guide, docjson_path))
                return True

            inst.label_document = label_doc
            return inst

        with patch(
            "agentic_extract.labeling.workflow.LabelingAgent",
            side_effect=make_mock_agent,
        ):
            result = await tool()
            text = _tool_text(result)

        assert "总计: 3 篇文档" in text
        assert "成功: 3 篇" in text
        assert "失败: 0 篇" in text
        assert {doc_id for doc_id, _, _ in labeled} == {"t1", "t2", "e1"}
        assert all("测试指导" == guide for _, guide, _ in labeled)

    @pytest.mark.asyncio
    async def test_label_partial_failure(self, initialized_workspace):
        """部分文档标注失败"""
        (initialized_workspace / "business_guide.md").write_text("guide", encoding="utf-8")
        for doc_id in ("t1", "t2"):
            _write_docjson(doc_id)

        tool = self._create_tool()
        call_results = {"t1": True, "t2": False}

        def make_mock_agent(**kwargs):
            inst = MagicMock()

            async def label_doc(doc_id, schema_json, business_guide, docjson_path):
                _ = (schema_json, business_guide, docjson_path)
                return call_results[doc_id]

            inst.label_document = label_doc
            return inst

        with patch(
            "agentic_extract.labeling.workflow.LabelingAgent",
            side_effect=make_mock_agent,
        ):
            result = await tool()
            text = _tool_text(result)

        assert "失败: 1 篇" in text
        assert "失败文档: t2" in text

    @pytest.mark.asyncio
    async def test_label_specified_doc_ids(self, initialized_workspace):
        """指定 doc_ids 只标注指定文档"""
        (initialized_workspace / "business_guide.md").write_text("guide", encoding="utf-8")
        for doc_id in ("t1", "t2", "e2"):
            _write_docjson(doc_id)

        tool = self._create_tool()
        labeled_docs = []

        def make_mock_agent(**kwargs):
            inst = MagicMock()

            async def label_doc(doc_id, schema_json, business_guide, docjson_path):
                _ = (schema_json, business_guide, docjson_path)
                labeled_docs.append(doc_id)
                return True

            inst.label_document = label_doc
            return inst

        with patch(
            "agentic_extract.labeling.workflow.LabelingAgent",
            side_effect=make_mock_agent,
        ):
            result = await tool(doc_ids="t1,e2,missing")
            text = _tool_text(result)

        assert "总计: 2 篇文档" in text
        assert set(labeled_docs) == {"t1", "e2"}

    @pytest.mark.asyncio
    async def test_label_without_guide_uses_fallback(self, initialized_workspace):
        """没有 business_guide.md 时使用兜底文本"""
        _write_docjson("d1")
        tool = self._create_tool()
        captured_guide = []

        def make_mock_agent(**kwargs):
            inst = MagicMock()

            async def label_doc(doc_id, schema_json, business_guide, docjson_path):
                _ = (doc_id, schema_json, docjson_path)
                captured_guide.append(business_guide)
                return True

            inst.label_document = label_doc
            return inst

        with patch(
            "agentic_extract.labeling.workflow.LabelingAgent",
            side_effect=make_mock_agent,
        ):
            await tool()

        assert len(captured_guide) == 1
        assert "无业务指导文档" in captured_guide[0]
