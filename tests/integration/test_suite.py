"""
xdev 套件集成测试

测试完整工作流：init → import → list/doc → schema → label → run → eval
以及配置管理和 skills 导出。
"""

import json
import os
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

# --- fixtures ---

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
PDFS_DIR = FIXTURES_DIR / "pdfs"
DOCJSON_DIR = FIXTURES_DIR / "docjson"

SAMPLE_IDS = ["sample_001", "sample_002", "sample_003"]

# 年报的简单 schema：公司名称 + 证券代码
TEST_SCHEMA = {
    "type": "object",
    "data": {
        "公司名称": "str",
        "证券代码": "str",
    },
}

# 标注数据（从文档内容中手工提取）
TEST_LABELS = {
    "sample_001": {
        "公司名称": "深圳市富恒新材料股份有限公司",
        "证券代码": "832469",
    },
    "sample_002": {
        "公司名称": "",  # 需要运行后确认
        "证券代码": "",
    },
    "sample_003": {
        "公司名称": "",
        "证券代码": "",
    },
}

# 测试用的 program.py（Document 模式，简单正则提取）
TEST_PROGRAM = """\
import re
from code_executor.document.models import Document

def extract(document: Document):
    text = "\\n".join(document.get_all_texts())

    result = {"公司名称": "", "证券代码": ""}

    # 提取证券代码
    m = re.search(r"证券代码[：:]\\s*(\\d{6})", text)
    if m:
        result["证券代码"] = m.group(1)

    # 提取公司名称（"XX公司" 模式）
    m = re.search(r"([\\u4e00-\\u9fa5]{2,}(?:股份有限公司|有限公司))", text)
    if m:
        result["公司名称"] = m.group(1)

    return result
"""

# flat 模式示例（用于验证 xdev 强制 Document 输入）
FLAT_TEST_PROGRAM = """\
def extract(article):
    return {"公司名称": "", "证券代码": ""}
"""


@pytest.fixture
def workspace(tmp_path):
    """创建临时 workspace 并返回路径"""
    ws = tmp_path / "workspace"
    return ws


@pytest.fixture
def populated_workspace(workspace):
    """创建已导入数据的 workspace"""
    from xdev.workspace import init_workspace
    from xdev.import_data import import_from_data_dir

    init_workspace(workspace)

    # 准备数据源目录（模拟 .xdev 结构）
    source_dir = workspace.parent / "source_data"
    (source_dir / "data" / "docjson").mkdir(parents=True)
    (source_dir / "data" / "pdf").mkdir(parents=True)
    (source_dir / "labels").mkdir(parents=True)

    for sid in SAMPLE_IDS:
        shutil.copy2(DOCJSON_DIR / f"{sid}.json", source_dir / "data" / "docjson" / f"{sid}.json")
        shutil.copy2(PDFS_DIR / f"{sid}.pdf", source_dir / "data" / "pdf" / f"{sid}.pdf")

    # 导入数据
    data_dir = workspace / ".xdev"
    import_from_data_dir(str(source_dir), str(data_dir))

    return workspace


@pytest.fixture
def ready_workspace(populated_workspace):
    """创建完整可评估的 workspace（含 schema + labels + program）"""
    ws = populated_workspace
    data_dir = ws / ".xdev"

    # 写入 schema
    with open(data_dir / "schema.json", "w", encoding="utf-8") as f:
        json.dump(TEST_SCHEMA, f, ensure_ascii=False, indent=2)

    # 写入 program.py
    with open(ws / "program.py", "w", encoding="utf-8") as f:
        f.write(TEST_PROGRAM)

    # 先运行提取，获取实际输出作为标注（自举方式）
    from xdev.evaluation import run_single_extraction

    for sid in SAMPLE_IDS:
        result = run_single_extraction(sid, str(data_dir), str(ws))
        label_path = data_dir / "labels" / f"{sid}.json"
        with open(label_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    return ws


# --- test: init ---


class TestInit:
    """测试 xdev init"""

    def test_creates_directory_structure(self, workspace):
        from xdev.workspace import init_workspace

        init_workspace(workspace)

        assert workspace.exists()
        assert (workspace / ".git").exists()
        assert (workspace / ".gitignore").exists()
        assert (workspace / ".xdev").exists()
        assert (workspace / ".xdev" / "data" / "docjson").exists()
        assert (workspace / ".xdev" / "data" / "pdf").exists()
        assert (workspace / ".xdev" / "labels").exists()
        assert (workspace / "program.py").exists()
        assert (workspace / "tests" / "conftest.py").exists()
        assert (workspace / "tests" / "test_extract.py").exists()
        assert (workspace / "docs").exists()
        assert not (workspace / "docs" / "data_issues.md").exists()
        assert not (workspace / "docs" / "known_limitations.md").exists()
        assert not (workspace / "docs" / "notes.md").exists()

        program_content = (workspace / "program.py").read_text(encoding="utf-8")
        assert "def extract(document: Document, tool_hub: ToolHub)" in program_content
        assert "def extract(article" not in program_content

    def test_idempotent(self, workspace):
        """重复初始化不应覆盖已有文件"""
        from xdev.workspace import init_workspace

        init_workspace(workspace)

        # 修改 program.py
        program = workspace / "program.py"
        program.write_text("# custom content", encoding="utf-8")

        # 再次初始化
        init_workspace(workspace)

        # 应该保留自定义内容
        assert program.read_text(encoding="utf-8") == "# custom content"


# --- test: import ---


class TestImportData:
    """测试数据导入"""

    def test_import_from_data_dir(self, workspace):
        from xdev.workspace import init_workspace
        from xdev.import_data import import_from_data_dir

        init_workspace(workspace)

        # 准备数据源
        source_dir = workspace.parent / "source_data"
        (source_dir / "data" / "docjson").mkdir(parents=True)
        (source_dir / "data" / "pdf").mkdir(parents=True)

        for sid in SAMPLE_IDS:
            shutil.copy2(DOCJSON_DIR / f"{sid}.json", source_dir / "data" / "docjson" / f"{sid}.json")
            shutil.copy2(PDFS_DIR / f"{sid}.pdf", source_dir / "data" / "pdf" / f"{sid}.pdf")

        data_dir = workspace / ".xdev"
        import_from_data_dir(str(source_dir), str(data_dir))

        # 验证
        assert (data_dir / "manifest.json").exists()
        assert len(list((data_dir / "data" / "docjson").glob("*.json"))) == 3
        assert len(list((data_dir / "data" / "pdf").glob("*.pdf"))) == 3

    def test_manifest_content(self, populated_workspace):
        from xdev.api import get_manifest

        data_dir = populated_workspace / ".xdev"
        manifest = get_manifest(str(data_dir))

        assert manifest is not None
        assert manifest.doc_count == 3
        assert manifest.source.type == "data-dir"
        assert manifest.imported_at  # 非空


# --- test: list & doc ---


class TestListAndDoc:
    """测试文档列表和查看"""

    def test_list_doc_ids(self, populated_workspace):
        from xdev.api import list_doc_ids

        data_dir = populated_workspace / ".xdev"
        doc_ids = list_doc_ids(str(data_dir))

        assert len(doc_ids) == 3
        assert set(doc_ids) == set(SAMPLE_IDS)

    def test_get_docjson_path(self, populated_workspace):
        from xdev.api import get_docjson_path

        data_dir = populated_workspace / ".xdev"
        path = get_docjson_path("sample_001", str(data_dir))

        assert path.exists()
        assert path.name == "sample_001.json"

    def test_get_pdf_path(self, populated_workspace):
        from xdev.api import get_pdf_path

        data_dir = populated_workspace / ".xdev"
        path = get_pdf_path("sample_001", str(data_dir))

        assert path.exists()
        assert path.name == "sample_001.pdf"

    def test_doc_content_readable(self, populated_workspace):
        """验证 docjson 能转换为纯文本"""
        from xdev.api import get_docjson_path
        from code_executor.loader import to_plain_article

        data_dir = populated_workspace / ".xdev"
        docjson_path = get_docjson_path("sample_001", str(data_dir))

        with open(docjson_path, "r", encoding="utf-8") as f:
            docjson = json.load(f)

        text = to_plain_article(docjson)
        assert isinstance(text, (str, list))
        assert len(text) > 0


# --- test: schema & label ---


class TestSchemaAndLabel:
    """测试 schema 和标注管理"""

    def test_schema_read(self, populated_workspace):
        from xdev.api import get_schema

        data_dir = populated_workspace / ".xdev"

        # 写入 schema
        with open(data_dir / "schema.json", "w", encoding="utf-8") as f:
            json.dump(TEST_SCHEMA, f, ensure_ascii=False)

        schema = get_schema(str(data_dir))

        assert schema is not None
        assert schema.type == "object"
        assert "公司名称" in schema.data
        assert "证券代码" in schema.data

    def test_label_write_and_read(self, populated_workspace):
        from xdev.api import get_label_path, get_label, list_labeled_doc_ids

        data_dir = populated_workspace / ".xdev"

        # 写入标注
        label_data = {"公司名称": "测试公司", "证券代码": "000001"}
        label_path = get_label_path("sample_001", str(data_dir))
        with open(label_path, "w", encoding="utf-8") as f:
            json.dump(label_data, f, ensure_ascii=False)

        # 读取标注
        label = get_label("sample_001", str(data_dir))
        assert label == label_data

        # 列出已标注
        labeled = list_labeled_doc_ids(str(data_dir))
        assert "sample_001" in labeled

    def test_no_label_returns_none(self, populated_workspace):
        from xdev.api import get_label

        data_dir = populated_workspace / ".xdev"
        label = get_label("sample_001", str(data_dir))
        assert label is None


# --- test: run ---


class TestRun:
    """测试单文档提取"""

    def test_run_single_extraction(self, populated_workspace):
        from xdev.evaluation import run_single_extraction

        ws = populated_workspace
        data_dir = ws / ".xdev"

        # 写入 schema（run 不需要 schema，但确保环境完整）
        with open(data_dir / "schema.json", "w", encoding="utf-8") as f:
            json.dump(TEST_SCHEMA, f, ensure_ascii=False)

        # 写入 program.py
        with open(ws / "program.py", "w", encoding="utf-8") as f:
            f.write(TEST_PROGRAM)

        result = run_single_extraction("sample_001", str(data_dir), str(ws))

        assert isinstance(result, dict)
        assert "公司名称" in result
        assert "证券代码" in result
        # 验证提取结果非空
        assert result["证券代码"] == "832469"
        assert "富恒" in result["公司名称"]

    def test_run_rejects_flat_mode_program(self, populated_workspace):
        from xdev.evaluation import run_single_extraction

        ws = populated_workspace
        data_dir = ws / ".xdev"

        with open(ws / "program.py", "w", encoding="utf-8") as f:
            f.write(FLAT_TEST_PROGRAM)

        with pytest.raises(ValueError, match="仅支持 Document 输入"):
            run_single_extraction("sample_001", str(data_dir), str(ws))

    def test_run_single_extraction_from_docjson_file(self, populated_workspace):
        from xdev.evaluation import run_single_extraction_from_file

        ws = populated_workspace
        data_dir = ws / ".xdev"

        with open(data_dir / "schema.json", "w", encoding="utf-8") as f:
            json.dump(TEST_SCHEMA, f, ensure_ascii=False)

        with open(ws / "program.py", "w", encoding="utf-8") as f:
            f.write(TEST_PROGRAM)

        result = run_single_extraction_from_file(
            workspace=str(ws),
            docjson_path=str(data_dir / "data" / "docjson" / "sample_001.json"),
        )

        assert isinstance(result, dict)
        assert result["证券代码"] == "832469"
        assert "富恒" in result["公司名称"]

    def test_run_single_extraction_from_pdf_file(self, populated_workspace, monkeypatch):
        from xdev.evaluation import run_single_extraction_from_file

        ws = populated_workspace
        data_dir = ws / ".xdev"

        with open(data_dir / "schema.json", "w", encoding="utf-8") as f:
            json.dump(TEST_SCHEMA, f, ensure_ascii=False)

        with open(ws / "program.py", "w", encoding="utf-8") as f:
            f.write(TEST_PROGRAM)

        sample_docjson = json.loads((data_dir / "data" / "docjson" / "sample_001.json").read_text(encoding="utf-8"))

        monkeypatch.setattr(
            "xdev.evaluation.prepare_extraction_runtime",
            lambda: type(
                "Runtime",
                (),
                {
                    "memect_api_base": "http://pdf-parser/api",
                    "concurrent": 16,
                    "tool_hub": None,
                },
            )(),
        )
        monkeypatch.setattr(
            "code_executor.document.utils.pdf_parser.parse_pdf_file_to_docjson",
            lambda _path, api_url=None: sample_docjson,
        )

        result = run_single_extraction_from_file(
            workspace=str(ws),
            pdf_path=str(data_dir / "data" / "pdf" / "sample_001.pdf"),
        )

        assert isinstance(result, dict)
        assert result["证券代码"] == "832469"
        assert "富恒" in result["公司名称"]

    def test_run_single_extraction_from_file_requires_exactly_one_input(self, populated_workspace):
        from xdev.evaluation import run_single_extraction_from_file

        ws = populated_workspace

        with open(ws / "program.py", "w", encoding="utf-8") as f:
            f.write(TEST_PROGRAM)

        with pytest.raises(ValueError, match="必须且只能提供 pdf_path 或 docjson_path 之一"):
            run_single_extraction_from_file(workspace=str(ws))

    def test_cli_run_requires_exactly_one_input_mode(self, populated_workspace):
        from xdev.cli import cli

        ws = populated_workspace
        data_dir = ws / ".xdev"

        result = CliRunner().invoke(
            cli,
            [
                "run",
                "sample_001",
                "--pdf",
                str(data_dir / "data" / "pdf" / "sample_001.pdf"),
                "--workspace",
                str(ws),
            ],
        )

        assert result.exit_code != 0
        assert "必须且只能指定一种输入" in result.output


# --- test: eval ---


class TestEval:
    """测试评估"""

    def test_full_evaluation(self, ready_workspace):
        """完整评估（标注 = 提取结果，准确率应为 100%）"""
        from xdev.evaluation import run_evaluation

        ws = ready_workspace
        data_dir = ws / ".xdev"

        eval_result = run_evaluation(data_dir=str(data_dir), workspace=str(ws))

        assert eval_result.overall_accuracy == 1.0
        assert eval_result.total_records == len(SAMPLE_IDS)
        assert set(eval_result.field_stats.keys()) == set(TEST_SCHEMA["data"].keys())

    def test_single_doc_evaluation(self, ready_workspace):
        """单文档评估"""
        from xdev.evaluation import run_evaluation

        ws = ready_workspace
        data_dir = ws / ".xdev"

        eval_result = run_evaluation(
            doc_ids=["sample_001"],
            data_dir=str(data_dir),
            workspace=str(ws),
        )

        assert eval_result.overall_accuracy == 1.0
        assert eval_result.total_records == 1
        assert set(eval_result.field_stats.keys()) == set(TEST_SCHEMA["data"].keys())

    def test_eval_without_labels_raises(self, populated_workspace):
        """无标注时评估应该报错"""
        from xdev.evaluation import run_evaluation

        ws = populated_workspace
        data_dir = ws / ".xdev"

        # 写入 schema 和 program
        with open(data_dir / "schema.json", "w", encoding="utf-8") as f:
            json.dump(TEST_SCHEMA, f, ensure_ascii=False)
        with open(ws / "program.py", "w", encoding="utf-8") as f:
            f.write(TEST_PROGRAM)

        with pytest.raises(ValueError, match="没有可用的标注数据"):
            run_evaluation(data_dir=str(data_dir), workspace=str(ws))

    def test_eval_rejects_flat_mode_program(self, ready_workspace):
        from xdev.evaluation import run_evaluation

        ws = ready_workspace
        data_dir = ws / ".xdev"

        with open(ws / "program.py", "w", encoding="utf-8") as f:
            f.write(FLAT_TEST_PROGRAM)

        with pytest.raises(ValueError, match="仅支持 Document 输入"):
            run_evaluation(data_dir=str(data_dir), workspace=str(ws))


# --- test: config ---


class TestConfig:
    """测试配置管理"""

    def test_default_config(self):
        from xdev.config import XdevConfig
        from code_executor.tools.tool_setup.settings import (
            DEFAULT_EXTRACT_MAX_CONTENT_LENGTH,
            DEFAULT_LLM_SELECT_MAX_CONTENT_LENGTH,
        )

        config = XdevConfig()
        assert config.data_dir == ".xdev"
        assert config.concurrent == 16
        assert DEFAULT_EXTRACT_MAX_CONTENT_LENGTH == 50000
        assert DEFAULT_LLM_SELECT_MAX_CONTENT_LENGTH == 50000

    def test_project_config(self, populated_workspace):
        from xdev.config import load_config

        data_dir = populated_workspace / ".xdev"

        # 写入项目配置
        config_data = {"concurrent": 16, "base_url": "http://test:9999"}
        with open(data_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        # chdir 到 workspace 使项目配置生效
        old_cwd = os.getcwd()
        try:
            os.chdir(str(populated_workspace))
            config = load_config()
            assert config.concurrent == 16
            assert config.base_url == "http://test:9999"
        finally:
            os.chdir(old_cwd)

    def test_global_config(self, tmp_path, monkeypatch):
        from xdev.config import load_config

        # 创建全局配置
        global_config_dir = tmp_path / ".config" / "xdev"
        global_config_dir.mkdir(parents=True)
        config_data = {"concurrent": 32}
        with open(global_config_dir / "config.json", "w") as f:
            json.dump(config_data, f)

        # mock HOME
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # chdir 到没有项目配置的目录
        old_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            config = load_config()
            assert config.concurrent == 32
        finally:
            os.chdir(old_cwd)

    def test_env_override(self, monkeypatch):
        from xdev.config import load_config

        monkeypatch.setenv("XDEV_CONCURRENT", "64")
        config = load_config()
        assert config.concurrent == 64

    def test_priority_order(self, populated_workspace, monkeypatch):
        """环境变量 > 项目配置"""
        from xdev.config import load_config

        # 项目配置
        data_dir = populated_workspace / ".xdev"
        with open(data_dir / "config.json", "w") as f:
            json.dump({"concurrent": 16}, f)

        # 环境变量
        monkeypatch.setenv("XDEV_CONCURRENT", "64")

        old_cwd = os.getcwd()
        try:
            os.chdir(str(populated_workspace))
            config = load_config()
            assert config.concurrent == 64  # 环境变量优先
        finally:
            os.chdir(old_cwd)


# --- test: export-skills ---


class TestExportSkills:
    """测试 skills 导出"""

    def test_export_zip(self, tmp_path):
        from xdev.skills import export_skills

        output = tmp_path / "skills.zip"
        export_skills(output)

        assert output.exists()
        assert output.stat().st_size > 0

    def test_zip_content(self, tmp_path):
        import zipfile
        from xdev.skills import export_skills

        output = tmp_path / "skills.zip"
        export_skills(output)

        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()

            # 验证包含所有 5 个 skills
            assert "xdev/SKILL.md" in names
            assert "pdf_ai_explorer/SKILL.md" in names
            assert "extract_workflow/SKILL.md" in names
            assert "fact-extract/SKILL.md" in names
            assert "release_process/SKILL.md" in names

            # 验证内容非空
            for name in names:
                content = zf.read(name)
                assert len(content) > 0

    def test_default_filename(self):
        from xdev.skills import get_default_output_filename

        filename = get_default_output_filename()
        assert filename.startswith("extract-skills-")
        assert filename.endswith(".zip")
