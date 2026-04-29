"""
统一 execute() 接口单元测试

测试重构后的 execute() 函数：
- 参数验证（输入源互斥、数据格式互斥）
- 输入源：program / program_path / workspace
- 数据格式：data / docjson
- capture_output 模式
- DeprecationWarning 触发
"""

import pytest
import tempfile
import warnings
from pathlib import Path

from code_executor import execute, create_input
from code_executor.executor import (
    execute_from_file,
    execute_from_workspace,
    execute_from_file_on_docjson,
    execute_from_workspace_on_docjson,
    execute_with_output,
    do_extract,
    do_extract_with_output,
)
from code_executor.api import batch_execute_on_docjsons, execute_on_docjson


# ============================================================================
# 测试数据
# ============================================================================

SIMPLE_PROGRAM = '''
def extract(article):
    return {"title": article[0] if article else "empty"}
'''

SIMPLE_PROGRAM_TREE = '''
from code_executor.document.models.document import Document

def extract(doc: Document):
    # 使用 iter_nodes 获取标题
    for node in doc.iter_nodes("title"):
        return {"title": node.text}
    return {"title": "empty"}
'''

SIMPLE_DOCJSON = {
    "tree": {
        "root": {
            "type": "title",
            "data": {"text": "测试标题"},
            "children": [
                {
                    "type": "section",
                    "data": {"textlines": [{"text": "段落内容"}]}
                }
            ]
        }
    }
}


# ============================================================================
# 参数验证测试
# ============================================================================

class TestParameterValidation:
    """测试参数验证"""

    @pytest.mark.asyncio
    async def test_no_input_source_raises_error(self):
        """测试没有提供输入源时抛出错误"""
        with pytest.raises(ValueError, match="必须提供 program、program_path 或 workspace 之一"):
            await execute(data=["test"])

    @pytest.mark.asyncio
    async def test_multiple_input_sources_raises_error(self):
        """测试提供多个输入源时抛出错误"""
        with pytest.raises(ValueError, match="只能提供一个"):
            await execute(program=SIMPLE_PROGRAM, program_path="/fake/path", data=["test"])

    @pytest.mark.asyncio
    async def test_program_and_workspace_raises_error(self):
        """测试同时提供 program 和 workspace 时抛出错误"""
        with pytest.raises(ValueError, match="只能提供一个"):
            await execute(program=SIMPLE_PROGRAM, workspace="/fake/path", data=["test"])

    @pytest.mark.asyncio
    async def test_no_data_source_raises_error(self):
        """测试没有提供数据源时抛出错误"""
        with pytest.raises(ValueError, match="必须提供 data 或 docjson 之一"):
            await execute(program=SIMPLE_PROGRAM)

    @pytest.mark.asyncio
    async def test_multiple_data_sources_raises_error(self):
        """测试提供多个数据源时抛出错误"""
        with pytest.raises(ValueError, match="data 和 docjson 不能同时提供"):
            await execute(program=SIMPLE_PROGRAM, data=["test"], docjson=SIMPLE_DOCJSON)


# ============================================================================
# 输入源测试
# ============================================================================

class TestInputSources:
    """测试不同输入源"""

    @pytest.mark.asyncio
    async def test_execute_with_program_string(self):
        """测试使用代码字符串"""
        result = await execute(program=SIMPLE_PROGRAM, data=["标题内容"])
        assert result == {"title": "标题内容"}

    @pytest.mark.asyncio
    async def test_execute_with_program_path(self):
        """测试使用文件路径"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(SIMPLE_PROGRAM)
            f.flush()
            program_path = f.name

        try:
            result = await execute(program_path=program_path, data=["标题内容"])
            assert result == {"title": "标题内容"}
        finally:
            Path(program_path).unlink()

    @pytest.mark.asyncio
    async def test_execute_with_workspace(self):
        """测试使用 workspace 目录"""
        with tempfile.TemporaryDirectory() as workspace:
            # 创建 program.py
            program_path = Path(workspace) / "program.py"
            program_path.write_text(SIMPLE_PROGRAM)

            result = await execute(workspace=workspace, data=["标题内容"])
            assert result == {"title": "标题内容"}

    @pytest.mark.asyncio
    async def test_execute_with_workspace_path_object(self):
        """测试使用 Path 对象作为 workspace"""
        with tempfile.TemporaryDirectory() as workspace:
            workspace_path = Path(workspace)
            program_path = workspace_path / "program.py"
            program_path.write_text(SIMPLE_PROGRAM)

            result = await execute(workspace=workspace_path, data=["标题内容"])
            assert result == {"title": "标题内容"}


# ============================================================================
# 数据格式测试
# ============================================================================

class TestDataFormats:
    """测试不同数据格式"""

    @pytest.mark.asyncio
    async def test_execute_with_data_list(self):
        """测试使用已转换的 list 数据"""
        result = await execute(program=SIMPLE_PROGRAM, data=["标题", "内容"])
        assert result == {"title": "标题"}

    @pytest.mark.asyncio
    async def test_execute_with_docjson(self):
        """测试使用 docjson"""
        result = await execute(program=SIMPLE_PROGRAM_TREE, docjson=SIMPLE_DOCJSON)
        assert "title" in result
        assert "测试标题" in result["title"]

    @pytest.mark.asyncio
    async def test_execute_with_docjson_tree_mode(self):
        """测试 docjson 配合 tree mode 程序"""
        with tempfile.TemporaryDirectory() as workspace:
            program_path = Path(workspace) / "program.py"
            program_path.write_text(SIMPLE_PROGRAM_TREE)

            result = await execute(workspace=workspace, docjson=SIMPLE_DOCJSON)
            assert "title" in result


# ============================================================================
# capture_output 测试
# ============================================================================

class TestCaptureOutput:
    """测试 capture_output 模式"""

    @pytest.mark.asyncio
    async def test_capture_output_false_returns_result_only(self):
        """测试 capture_output=False 只返回结果"""
        result = await execute(program=SIMPLE_PROGRAM, data=["标题"], capture_output=False)
        assert isinstance(result, dict)
        assert result == {"title": "标题"}

    @pytest.mark.asyncio
    async def test_capture_output_true_returns_tuple(self):
        """测试 capture_output=True 返回元组"""
        result = await execute(program=SIMPLE_PROGRAM, data=["标题"], capture_output=True)
        assert isinstance(result, tuple)
        assert len(result) == 3
        extracted, stdout, stderr = result
        assert extracted == {"title": "标题"}
        assert isinstance(stdout, str)
        assert isinstance(stderr, str)

    @pytest.mark.asyncio
    async def test_capture_output_captures_print(self):
        """测试 capture_output 捕获 print 输出"""
        program = '''
def extract(article):
    print("Hello from extract")
    return {"done": True}
'''
        result, stdout, stderr = await execute(program=program, data=[], capture_output=True)
        assert result == {"done": True}
        assert "Hello from extract" in stdout

    @pytest.mark.asyncio
    async def test_capture_output_captures_stderr(self):
        """测试 capture_output 捕获 stderr 输出"""
        program = '''
import sys
def extract(article):
    print("Error message", file=sys.stderr)
    return {"done": True}
'''
        result, stdout, stderr = await execute(program=program, data=[], capture_output=True)
        assert result == {"done": True}
        assert "Error message" in stderr


# ============================================================================
# 模式检测测试
# ============================================================================

class TestModeDetection:
    """测试输入模式自动检测"""

    @pytest.mark.asyncio
    async def test_flat_mode_by_param_name_raises(self):
        """测试 article 参数名不再触发 flat 模式，而是明确失败"""
        program = '''
def extract(article):
    return {"count": len(article)}
'''
        with pytest.raises(ValueError, match="仅支持 Document 输入"):
            await execute(program=program, docjson=SIMPLE_DOCJSON)

    @pytest.mark.asyncio
    async def test_tree_mode_by_type_annotation(self):
        """测试通过类型注解推断 tree 模式"""
        result = await execute(program=SIMPLE_PROGRAM_TREE, docjson=SIMPLE_DOCJSON)
        assert "title" in result

    @pytest.mark.asyncio
    async def test_data_mode_by_param_name_raises(self):
        """测试 data 参数名不再触发 flat 模式，而是明确失败"""
        program = '''
def extract(data):
    return {"items": len(data) if isinstance(data, list) else 0}
'''
        with pytest.raises(ValueError, match="仅支持 Document 输入"):
            await execute(program=program, docjson=SIMPLE_DOCJSON)

    @pytest.mark.asyncio
    async def test_list_annotation_raises(self):
        """测试 list 注解不再触发 flat 模式，而是明确失败"""
        program = '''
def extract(article: list):
    return {"items": len(article)}
'''
        with pytest.raises(ValueError, match="仅支持 Document 输入"):
            await execute(program=program, docjson=SIMPLE_DOCJSON)


# ============================================================================
# DeprecationWarning 测试
# ============================================================================

class TestDeprecationWarnings:
    """测试废弃函数触发 DeprecationWarning"""

    @pytest.mark.asyncio
    async def test_do_extract_triggers_warning(self):
        """测试 do_extract 触发警告"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await do_extract(SIMPLE_PROGRAM, ["test"])
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "execute(program=..., data=...)" in str(w[0].message)

    @pytest.mark.asyncio
    async def test_do_extract_with_output_triggers_warning(self):
        """测试 do_extract_with_output 触发警告"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await do_extract_with_output(SIMPLE_PROGRAM, ["test"])
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "capture_output=True" in str(w[0].message)

    @pytest.mark.asyncio
    async def test_execute_from_file_triggers_warning(self):
        """测试 execute_from_file 触发警告"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(SIMPLE_PROGRAM)
            f.flush()
            program_path = f.name

        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                await execute_from_file(program_path, ["test"])
                assert len(w) == 1
                assert issubclass(w[0].category, DeprecationWarning)
                assert "program_path" in str(w[0].message)
        finally:
            Path(program_path).unlink()

    @pytest.mark.asyncio
    async def test_execute_from_workspace_triggers_warning(self):
        """测试 execute_from_workspace 触发警告"""
        with tempfile.TemporaryDirectory() as workspace:
            program_path = Path(workspace) / "program.py"
            program_path.write_text(SIMPLE_PROGRAM)

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                await execute_from_workspace(workspace, ["test"])
                assert len(w) == 1
                assert issubclass(w[0].category, DeprecationWarning)
                assert "workspace" in str(w[0].message)

    @pytest.mark.asyncio
    async def test_execute_from_file_on_docjson_triggers_warning(self):
        """测试 execute_from_file_on_docjson 触发警告"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(SIMPLE_PROGRAM_TREE)
            f.flush()
            program_path = f.name

        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                await execute_from_file_on_docjson(program_path, SIMPLE_DOCJSON)
                assert len(w) == 1
                assert issubclass(w[0].category, DeprecationWarning)
        finally:
            Path(program_path).unlink()

    @pytest.mark.asyncio
    async def test_execute_from_workspace_on_docjson_triggers_warning(self):
        """测试 execute_from_workspace_on_docjson 触发警告"""
        with tempfile.TemporaryDirectory() as workspace:
            program_path = Path(workspace) / "program.py"
            program_path.write_text(SIMPLE_PROGRAM_TREE)

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                await execute_from_workspace_on_docjson(workspace, SIMPLE_DOCJSON)
                assert len(w) == 1
                assert issubclass(w[0].category, DeprecationWarning)

    @pytest.mark.asyncio
    async def test_execute_with_output_triggers_warning(self):
        """测试 execute_with_output 触发警告"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await execute_with_output(SIMPLE_PROGRAM, ["test"])
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)


# ============================================================================
# 错误处理测试
# ============================================================================

class TestErrorHandling:
    """测试错误处理"""

    @pytest.mark.asyncio
    async def test_invalid_program_path_raises_error(self):
        """测试无效的程序路径抛出错误"""
        with pytest.raises(FileNotFoundError):
            await execute(program_path="/nonexistent/path.py", data=["test"])

    @pytest.mark.asyncio
    async def test_invalid_workspace_raises_error(self):
        """测试无效的 workspace 抛出错误"""
        with pytest.raises(FileNotFoundError):
            await execute(workspace="/nonexistent/workspace", data=["test"])

    @pytest.mark.asyncio
    async def test_workspace_without_program_py_raises_error(self):
        """测试 workspace 缺少 program.py 抛出错误"""
        with tempfile.TemporaryDirectory() as workspace:
            with pytest.raises(FileNotFoundError, match="program.py"):
                await execute(workspace=workspace, data=["test"])

    @pytest.mark.asyncio
    async def test_syntax_error_in_program(self):
        """测试程序语法错误"""
        program = "def extract(data)\n  return data"  # 缺少冒号
        with pytest.raises(SyntaxError):
            await execute(program=program, data=["test"])

    @pytest.mark.asyncio
    async def test_missing_extract_function(self):
        """测试缺少 extract 函数"""
        program = "def other_func(data): return data"
        with pytest.raises(ValueError, match="FunctionNotFound"):
            await execute(program=program, data=["test"])


# ============================================================================
# 兼容性测试
# ============================================================================

class TestBackwardCompatibility:
    """测试向后兼容性"""

    @pytest.mark.asyncio
    async def test_deprecated_functions_still_work(self):
        """测试废弃函数仍然可用"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            
            # do_extract
            result1 = await do_extract(SIMPLE_PROGRAM, ["test"])
            assert result1 == {"title": "test"}
            
            # do_extract_with_output
            result2, stdout, stderr = await do_extract_with_output(SIMPLE_PROGRAM, ["test"])
            assert result2 == {"title": "test"}

    @pytest.mark.asyncio
    async def test_create_input_still_works(self):
        """测试 create_input 仍然可用"""
        document = create_input(SIMPLE_DOCJSON)
        assert document.get_all_texts()
        
        result = await execute(program=SIMPLE_PROGRAM_TREE, data=document)
        assert "title" in result

    def test_create_input_flat_mode_raises(self):
        """测试 create_input 不再支持 flat 模式"""
        with pytest.raises(ValueError, match="仅支持 Document 输入"):
            create_input(SIMPLE_DOCJSON, mode="flat")


class TestToolHubInjection:
    """测试显式 ToolHub 注入"""

    @pytest.mark.asyncio
    async def test_extract_can_receive_tool_hub_by_name(self):
        program = '''
from code_executor.document.models.document import Document

def extract(document: Document, tool_hub):
    return {
        "texts": document.get_all_texts(),
        "tool": tool_hub["name"],
    }
'''
        result = await execute(
            program=program,
            docjson=SIMPLE_DOCJSON,
            tool_hub={"name": "fake-hub"},
        )

        assert result["tool"] == "fake-hub"
        assert "测试标题" in result["texts"]

    @pytest.mark.asyncio
    async def test_extract_can_receive_tool_hub_as_second_positional_param(self):
        program = '''
from code_executor.document.models.document import Document

def extract(document: Document, hub):
    return {"tool": hub["name"]}
'''
        result = await execute(
            program=program,
            docjson=SIMPLE_DOCJSON,
            tool_hub={"name": "fake-hub"},
        )

        assert result == {"tool": "fake-hub"}

    @pytest.mark.asyncio
    async def test_extract_without_tool_hub_param_still_works(self):
        result = await execute(
            program=SIMPLE_PROGRAM_TREE,
            docjson=SIMPLE_DOCJSON,
            tool_hub={"name": "ignored"},
        )

        assert result["title"] == "测试标题"

    @pytest.mark.asyncio
    async def test_execute_on_docjson_passes_tool_hub(self):
        program = '''
from code_executor.document.models.document import Document

def extract(document: Document, tool_hub):
    return {"tool": tool_hub["name"], "texts": document.get_all_texts()}
'''
        result = await execute_on_docjson(
            SIMPLE_DOCJSON,
            program=program,
            tool_hub={"name": "api-hub"},
        )

        assert result["tool"] == "api-hub"
        assert "测试标题" in result["texts"]

    @pytest.mark.asyncio
    async def test_execute_on_docjson_config_mode_raises(self):
        with pytest.raises(ValueError, match="config/flat 旧格式已不再支持"):
            await execute_on_docjson(
                SIMPLE_DOCJSON,
                config={"field": "def extract(article): return {'field': ''}"},
            )

    @pytest.mark.asyncio
    async def test_batch_execute_on_docjsons_passes_tool_hub(self):
        program = '''
from code_executor.document.models.document import Document

def extract(document: Document, tool_hub):
    return {"tool": tool_hub["name"], "count": len(document.get_all_texts())}
'''
        results = await batch_execute_on_docjsons(
            program,
            [SIMPLE_DOCJSON, SIMPLE_DOCJSON],
            tool_hub={"name": "batch-hub"},
        )

        assert [result["success"] for result in results] == [True, True]
        assert [result["data"]["tool"] for result in results] == ["batch-hub", "batch-hub"]

    @pytest.mark.asyncio
    async def test_deprecated_docjson_file_wrapper_passes_tool_hub(self):
        program = '''
from code_executor.document.models.document import Document

def extract(document: Document, tool_hub):
    return {"tool": tool_hub["name"]}
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(program)
            f.flush()
            program_path = f.name

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                result = await execute_from_file_on_docjson(
                    program_path,
                    SIMPLE_DOCJSON,
                    tool_hub={"name": "file-wrapper-hub"},
                )
        finally:
            Path(program_path).unlink()

        assert result == {"tool": "file-wrapper-hub"}

    @pytest.mark.asyncio
    async def test_deprecated_docjson_workspace_wrapper_passes_tool_hub(self):
        program = '''
from code_executor.document.models.document import Document

def extract(document: Document, tool_hub):
    return {"tool": tool_hub["name"]}
'''
        with tempfile.TemporaryDirectory() as workspace:
            program_path = Path(workspace) / "program.py"
            program_path.write_text(program)

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                result = await execute_from_workspace_on_docjson(
                    workspace,
                    SIMPLE_DOCJSON,
                    tool_hub={"name": "workspace-wrapper-hub"},
                )

        assert result == {"tool": "workspace-wrapper-hub"}
