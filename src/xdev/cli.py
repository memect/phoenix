"""
xdev CLI 入口
"""

import click
from pathlib import Path

from .config import get_data_dir


@click.group()
def cli():
    """xdev - 数据管理和评估工具"""
    pass


def _classify_documents(evaluation_result):
    """按评估结果划分正确/错误文档 ID"""
    from evaluator.core.models import RecordDetailType

    correct_ids = []
    incorrect_ids = []

    for detail in evaluation_result.details:
        std_id = detail.standared_info.id
        if detail.type == RecordDetailType.CORRECT:
            correct_ids.append(std_id)
        elif detail.type == RecordDetailType.INCORRECT:
            incorrect_ids.append(std_id)

    return correct_ids, incorrect_ids


def _get_error_ids(evaluation_result, max_count: int = 10) -> list[str]:
    """获取提取报错文档 ID（最多 max_count 个）"""
    error_ids = []
    for detail in evaluation_result.details:
        extracted_info = detail.extracted_info
        if extracted_info and not extracted_info.success:
            error_ids.append(detail.standared_info.id)
            if len(error_ids) >= max_count:
                break
    return error_ids


def _print_evaluation_report(evaluation_result):
    """打印与 extract-dev train 对齐的评估报告"""
    field_stats = evaluation_result.field_stats
    field_count = len(field_stats)
    field_average = sum(stat.accuracy for stat in field_stats.values()) / field_count if field_count > 0 else 0.0

    click.echo("\n# 评估报告\n")

    # 总体指标
    click.echo("总体指标\n")
    click.echo(f"- **总体准确率**: {evaluation_result.overall_accuracy:.2%}")
    click.echo(f"- **字段平均准确率**: {field_average:.2%}")
    click.echo(f"- **文档数**: {evaluation_result.total_records}")
    click.echo(f"- **字段数**: {field_count}")
    click.echo(f"- **正确字段总数**: {evaluation_result.total_correct}\n")

    # 文档状态
    correct_ids, incorrect_ids = _classify_documents(evaluation_result)
    click.echo("文档状态\n")
    click.echo(f"- **正确文档数**: {len(correct_ids)}")
    click.echo(f"- **错误文档数**: {len(incorrect_ids)}\n")

    if incorrect_ids:
        click.echo("错误文档ID:")
        click.echo(", ".join(incorrect_ids) + "\n")

    # 字段统计
    click.echo("字段统计\n")
    click.echo("| 字段 | 准确率 | 召回率 | 精确率 | F1 |")
    click.echo("|------|--------|--------|--------|-----|")
    for field_name, stat in field_stats.items():
        click.echo(f"| {field_name} | {stat.accuracy:.2%} | {stat.recall:.2%} | {stat.precision:.2%} | {stat.f1:.2%} |")
    click.echo()

    # 提取报错文档
    error_ids = _get_error_ids(evaluation_result)
    if error_ids:
        total_errors = sum(1 for d in evaluation_result.details if d.extracted_info and not d.extracted_info.success)
        click.echo(f"提取报错的文档 ({total_errors} 个):\n")
        if total_errors > 10:
            click.echo(", ".join(error_ids) + ", ... (只显示前 10 个)\n")
        else:
            click.echo(", ".join(error_ids) + "\n")


@cli.command()
@click.option("--set-id", help="远程标准集 ID")
@click.option("--base-url", default="http://localhost:8008", help="标准集 API 地址")
@click.option("--pdfs", type=click.Path(exists=True), help="本地 PDF 目录（全量初始化）")
@click.option("--from-data-dir", type=click.Path(exists=True), help="从另一个 data-dir 导入")
@click.option("--source", type=click.Path(exists=True), help="数据源配置文件")
@click.option("--add-pdf", type=click.Path(exists=True), help="增量添加 PDF（文件或目录）")
@click.option("--reparse", is_flag=True, help="重新解析已有 PDF 生成新 DocJSON")
@click.option("--doc-ids", help="配合 --reparse 使用，逗号分隔的文档 ID")
@click.option("--force", is_flag=True, help="配合 --add-pdf 使用，覆盖已有文档")
@click.option("--std-ids", help="文档 ID 白名单（逗号分隔），配合 --set-id 使用")
@click.option("--std-ids-file", type=click.Path(exists=True), help="文档 ID 白名单文件（一行一个 ID），配合 --set-id 使用")
@click.option("--sync", is_flag=True, help="同步模式：导入后删除远程不存在的本地文档")
@click.option("--skip-exist", is_flag=True, help="跳过本地已有的文档，不重新下载")
@click.option("--data-dir", type=click.Path(), help="数据目录 (默认 .xdev)")
def import_data(set_id, base_url, pdfs, from_data_dir, source, add_pdf, reparse, doc_ids, force, std_ids, std_ids_file, sync, skip_exist, data_dir):
    """导入数据"""
    from .import_data import (
        import_from_set_id, import_from_pdfs, import_from_data_dir, import_from_source,
        add_pdfs, reparse_docs, warn_symlinks, resolve_std_ids,
    )

    # 检查互斥参数（六选一，或者全不选时从 manifest 读取）
    modes = [set_id, pdfs, from_data_dir, source, add_pdf, reparse]
    mode_count = sum(bool(s) for s in modes)

    if mode_count == 0 and (sync or skip_exist):
        # 无模式参数但有 sync/skip-exist，从 manifest 读取
        from .api import get_manifest
        manifest = get_manifest(data_dir)
        if manifest is None:
            click.echo("错误：manifest.json 不存在，请先运行 import-data", err=True)
            raise click.Abort()
        if manifest.source.type != "set-id":
            click.echo(f"错误：数据源类型为 {manifest.source.type}，--sync/--skip-exist 仅支持 set-id 类型", err=True)
            raise click.Abort()
        set_id = manifest.source.set_id
        base_url = manifest.source.base_url
        if std_ids is None and std_ids_file is None and manifest.source.std_ids is not None:
            std_ids = ",".join(manifest.source.std_ids)
    elif mode_count != 1:
        click.echo(
            "错误：必须指定且只能指定一个模式 "
            "(--set-id, --pdfs, --from-data-dir, --source, --add-pdf, --reparse)",
            err=True,
        )
        raise click.Abort()

    if force and not add_pdf:
        click.echo("错误：--force 只能与 --add-pdf 一起使用", err=True)
        raise click.Abort()

    if doc_ids and not reparse:
        click.echo("错误：--doc-ids 只能与 --reparse 一起使用", err=True)
        raise click.Abort()

    if (std_ids or std_ids_file) and not set_id:
        click.echo("错误：--std-ids / --std-ids-file 只能与 --set-id 一起使用", err=True)
        raise click.Abort()

    if (sync or skip_exist) and not set_id:
        click.echo("错误：--sync / --skip-exist 仅支持 set-id 数据源", err=True)
        raise click.Abort()

    warn_symlinks(data_dir)

    resolved_std_ids = resolve_std_ids(std_ids, std_ids_file)

    try:
        if set_id:
            import_from_set_id(set_id, base_url, data_dir, std_ids=resolved_std_ids, sync=sync, skip_exist=skip_exist)
        elif pdfs:
            import_from_pdfs(pdfs, data_dir)
        elif from_data_dir:
            import_from_data_dir(from_data_dir, data_dir)
        elif source:
            import_from_source(source, data_dir)
        elif add_pdf:
            add_pdfs(add_pdf, data_dir, force=force)
        elif reparse:
            ids = [s.strip() for s in doc_ids.split(",") if s.strip()] if doc_ids else None
            reparse_docs(ids, data_dir)
    except Exception as e:
        click.echo(f"导入失败: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option("--data-dir", type=click.Path(), help="数据目录 (默认 .xdev)")
def list(data_dir):
    """列出所有文档"""
    from .api import list_doc_ids, get_manifest

    doc_ids = list_doc_ids(data_dir)
    if not doc_ids:
        click.echo("错误：没有文档数据，请先运行 import-data", err=True)
        raise click.Abort()

    manifest = get_manifest(data_dir)
    if manifest:
        click.echo(f"数据源: {manifest.source.type}")
        click.echo(f"导入时间: {manifest.imported_at}")

    click.echo(f"文档数量: {len(doc_ids)}")
    click.echo()

    for doc_id in doc_ids:
        click.echo(doc_id)


@cli.command()
@click.argument("doc_id")
@click.option("--data-dir", type=click.Path(), help="数据目录 (默认 .xdev)")
def doc(doc_id, data_dir):
    """查看文档内容（Markdown格式）"""
    from .api import get_docjson_path
    import json

    docjson_path = get_docjson_path(doc_id, data_dir)

    if not docjson_path.exists():
        click.echo(f"错误：文档不存在: {doc_id}", err=True)
        raise click.Abort()

    with open(docjson_path, "r", encoding="utf-8") as f:
        docjson = json.load(f)

    # 使用 Document 模型获取纯文本
    from code_executor.document.models.document import Document
    document = Document.from_dict(docjson)
    texts = document.get_all_texts(max_items=None)
    text = "\n\n".join(texts)

    # Markdown 格式输出
    click.echo(f"# 文档: {doc_id}\n")
    click.echo(f"**DocJSON路径**: `{docjson_path}`\n")
    click.echo("---\n")

    # 字数限制
    if len(text) > 10000:
        click.echo(text[:1000])
        click.echo("\n---\n")
        click.echo(f"**文档过长** ({len(text)} 字符)，仅显示前 1000 字符。\n")
        click.echo("**使用 pdf-ai-explorer 查看完整内容**：\n")
        click.echo("```bash")
        click.echo("# 查看文档大纲（了解结构）")
        click.echo(f"pdf-ai-explorer outline {docjson_path}")
        click.echo("")
        click.echo("# 搜索关键词")
        click.echo(f'pdf-ai-explorer search {docjson_path} "关键词"')
        click.echo("")
        click.echo("# 按页码阅读")
        click.echo(f"pdf-ai-explorer read {docjson_path} 1-5")
        click.echo("")
        click.echo("# 按节点ID查看内容（从 outline 获取节点ID）")
        click.echo(f"pdf-ai-explorer content {docjson_path} <节点ID>")
        click.echo("```")
    else:
        click.echo(text)


@cli.command(name="label-guide")
@click.argument("doc_id", required=False)
@click.option("--data-dir", type=click.Path(), help="数据目录 (默认 .xdev)")
def label_guide(doc_id, data_dir):
    """输出标注指导"""
    from .api import get_schema, get_label_path, list_doc_ids
    import json

    schema = get_schema(data_dir)
    if schema is None:
        click.echo("错误：schema 未定义，请先创建 schema.json", err=True)
        click.echo()
        click.echo("schema.json 格式示例：")
        click.echo(json.dumps({
            "type": "object",
            "data": {
                "字段1": "str",
                "字段2": "float"
            }
        }, indent=2, ensure_ascii=False))
        raise click.Abort()

    data_dir_path = get_data_dir(data_dir)

    if doc_id is None:
        # 输出通用指导
        click.echo("# 标注指导")
        click.echo()
        click.echo("## Schema 文件")
        click.echo(f"路径: {data_dir_path / 'schema.json'}")
        click.echo(f"类型: {schema.type}")
        click.echo()
        click.echo("## 标注文件")
        click.echo(f"目录: {data_dir_path / 'labels'}/")
        click.echo("格式: <doc_id>.json")
        click.echo()
        click.echo("## 标注格式")

        if schema.type == "object":
            click.echo("每个文档标注一个对象：")
            example = {k: f"<{v}>" for k, v in schema.data.items()}
            click.echo(json.dumps(example, indent=2, ensure_ascii=False))
        else:
            click.echo("每个文档标注一个数组：")
            example = [{k: f"<{v}>" for k, v in schema.data.items()}]
            click.echo(json.dumps(example, indent=2, ensure_ascii=False))
    else:
        # 输出特定文档的标注模板
        doc_ids = list_doc_ids(data_dir)
        if doc_id not in doc_ids:
            click.echo(f"错误：文档不存在: {doc_id}", err=True)
            raise click.Abort()

        label_path = get_label_path(doc_id, data_dir)

        click.echo(f"# 文档 {doc_id} 标注指导")
        click.echo()
        click.echo(f"标注文件路径: {label_path}")
        click.echo()
        click.echo("标注模板：")

        if schema.type == "object":
            template = {k: "" for k in schema.data.keys()}
            click.echo(json.dumps(template, indent=2, ensure_ascii=False))
        else:
            template = [{k: "" for k in schema.data.keys()}]
            click.echo(json.dumps(template, indent=2, ensure_ascii=False))


@cli.command(name="label-status")
@click.option("--detail", is_flag=True, help="输出详细信息（列出每个问题文档）")
@click.option("--data-dir", type=click.Path(), help="数据目录 (默认 .xdev)")
def label_status(detail, data_dir):
    """检查标注状态"""
    from .api import check_label_status

    try:
        report = check_label_status(data_dir)
    except FileNotFoundError as e:
        click.echo(f"错误：{e}", err=True)
        raise click.Abort()

    click.echo("标注状态:")
    click.echo(f"  文档总数:       {report.total_docs}")
    click.echo(f"  已标注:         {report.labeled_count}")
    click.echo(f"  未标注:          {report.unlabeled_count}")
    click.echo(f"  Schema 不匹配:   {report.mismatched_count}")

    if detail:
        if report.unlabeled_ids:
            click.echo()
            click.echo("未标注文档:")
            for doc_id in report.unlabeled_ids:
                click.echo(f"  - {doc_id}")

        if report.issues:
            click.echo()
            click.echo("Schema 不匹配文档:")
            from collections import defaultdict
            by_doc: dict[str, list[str]] = defaultdict(list)
            for issue in report.issues:
                by_doc[issue.doc_id].append(issue.detail)
            for did in report.mismatched_ids:
                details = "; ".join(by_doc[did])
                click.echo(f"  - {did}: {details}")

    if report.all_good:
        click.echo()
        click.echo("结论: 所有文档已标注且与 schema 匹配 ✓")
    else:
        click.echo()
        click.echo(
            f"结论: 有 {report.needs_action_count} 篇文档需要处理"
            f"（{report.unlabeled_count} 未标注 + {report.mismatched_count} 不匹配）"
        )


@cli.command()
@click.argument("doc_id", required=False)
@click.option("--data-dir", type=click.Path(), help="数据目录 (默认 .xdev)")
@click.option("--workspace", type=click.Path(), help="workspace 目录 (默认当前目录)")
def eval(doc_id, data_dir, workspace):
    """运行评估"""
    from .evaluation import run_evaluation

    try:
        if doc_id:
            # 单文档评估
            doc_ids = [doc_id]
        else:
            # 全量评估
            doc_ids = None

        result = run_evaluation(doc_ids, data_dir, workspace)
        _print_evaluation_report(result)

    except Exception as e:
        click.echo(f"评估失败: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.argument("doc_id", required=False)
@click.option("--data-dir", type=click.Path(), help="数据目录 (默认 .xdev)")
@click.option("--workspace", type=click.Path(), help="workspace 目录 (默认当前目录)")
@click.option("--pdf", "pdf_path", type=click.Path(exists=True), help="直接对单个 PDF 执行提取")
@click.option("--docjson", "docjson_path", type=click.Path(exists=True), help="直接对单个 DocJSON 执行提取")
def run(doc_id, data_dir, workspace, pdf_path, docjson_path):
    """执行提取"""
    from .evaluation import run_single_extraction, run_single_extraction_from_file
    import json

    input_modes = [bool(doc_id), bool(pdf_path), bool(docjson_path)]
    if sum(input_modes) != 1:
        click.echo("提取失败: 必须且只能指定一种输入：doc_id、--pdf 或 --docjson", err=True)
        raise click.Abort()

    try:
        if doc_id:
            result = run_single_extraction(doc_id, data_dir, workspace)
        else:
            result = run_single_extraction_from_file(
                workspace=workspace,
                pdf_path=pdf_path,
                docjson_path=docjson_path,
            )

        click.echo("\n提取结果:")
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as e:
        click.echo(f"提取失败: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.argument("workspace", required=False)
def init(workspace):
    """初始化 workspace"""
    from .workspace import init_workspace

    if workspace is None:
        workspace = "workspace"

    workspace_path = Path(workspace).resolve()

    try:
        init_workspace(workspace_path)
        click.echo()
        click.echo("下一步:")
        click.echo(f"  cd {workspace}")
        click.echo("  xdev import-data --set-id <id>  # 或 --pdfs <dir>")
    except Exception as e:
        click.echo(f"初始化失败: {e}", err=True)
        raise click.Abort()


@cli.command(name="export-skills")
@click.option("--output", "-o", type=click.Path(), help="输出文件路径")
@click.option("--output-dir", type=click.Path(), help="输出目录（自动命名）")
def export_skills(output, output_dir):
    """导出 skills 到 ZIP 文件"""
    from .skills import export_skills as do_export, get_default_output_filename

    # 确定输出路径
    if output:
        output_path = Path(output)
    elif output_dir:
        output_path = Path(output_dir) / get_default_output_filename()
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = Path(get_default_output_filename())

    try:
        do_export(output_path)
    except Exception as e:
        click.echo(f"导出失败: {e}", err=True)
        raise click.Abort()


@cli.command(name="sync-pdfs")
@click.argument("pdf_dir", type=click.Path(exists=True))
@click.option("--data-dir", type=click.Path(), help="数据目录 (默认 .xdev)")
def sync_pdfs(pdf_dir, data_dir):
    """同步 PDF 目录到 .xdev/data/"""
    from .import_data import sync_pdfs as do_sync

    try:
        print(f"[sync-pdfs] 同步 PDF: {pdf_dir}")
        print("[sync-pdfs] 检查变更...")

        result = do_sync(pdf_dir, data_dir)

        print(f"[sync-pdfs] 新增: {len(result.added)} 篇")
        print(f"[sync-pdfs] 删除: {len(result.removed)} 篇 (保留 label)")
        print(f"[sync-pdfs] 修改: {len(result.modified)} 篇 (重新解析)")
        print(f"[sync-pdfs] 不变: {len(result.unchanged)} 篇")

        if result.total_changes > 0:
            total_current = len(result.added) + len(result.modified) + len(result.unchanged)
            print(f"[sync-pdfs] 完成。当前文档数: {total_current}")
        else:
            print("[sync-pdfs] 无变更")

    except Exception as e:
        click.echo(f"错误: {e}", err=True)
        raise click.Abort()


@cli.command(name="fix-symlinks")
@click.option("--fix", is_flag=True, help="修复符号链接（替换为真实文件副本）")
@click.option("--data-dir", type=click.Path(), help="数据目录 (默认 .xdev)")
def fix_symlinks_cmd(fix, data_dir):
    """检查和修复数据目录中的符号链接"""
    from .import_data import check_symlinks, fix_symlinks

    symlinks = check_symlinks(data_dir)
    if not symlinks:
        click.echo("数据目录中没有符号链接 ✓")
        return

    click.echo(f"发现 {len(symlinks)} 个符号链接：")
    for s in symlinks:
        click.echo(f"  {s} -> {s.resolve()}")

    if fix:
        fixed = fix_symlinks(data_dir)
        click.echo(f"\n已修复 {len(fixed)} 个符号链接")
    else:
        click.echo("\n使用 --fix 修复")


@cli.command()
@click.argument("workspace", default=".", type=click.Path(exists=True))
def migrate(workspace):
    """迁移旧格式 workspace (.cache/.extract-dev) 到 .xdev 格式"""
    from .migrate import migrate_legacy_workspace

    workspace_path = Path(workspace)
    if (workspace_path / ".xdev" / "manifest.json").exists():
        click.echo("已经是 .xdev 格式，无需迁移")
        return

    if not (workspace_path / ".cache").exists():
        click.echo("未检测到旧格式 workspace（没有 .cache/ 目录）")
        return

    result = migrate_legacy_workspace(workspace_path)
    if result:
        click.echo("迁移成功")
    else:
        click.echo("迁移失败")


@cli.command()
def context():
    """显示代码上下文（Document API 使用指南）"""
    click.echo("""# Document API 使用指南

## Document 核心方法

```python
from code_executor.document.models.document import Document

# 获取节点
node = document.get_node(node_id)

# 获取指定页面的所有节点
nodes = document.get_nodes_by_page(page_num)

# 遍历所有节点（可按类型过滤: "title", "section", "table", "figure"）
for node in document.iter_nodes(type_filter="title"):
    ...

# 获取所有段落文本（flat list）
texts = document.get_all_texts(max_items=100)

# 文档属性
document.total_pages
```

## Node 核心方法

```python
# 内容
node.get_title()        # 节点标题
node.get_text()         # 节点文本

# 导航
node.get_children()     # 子节点
node.get_parent()       # 父节点
node.collect_content()  # 递归收集后代内容 -> list[str | TableNode]

# 属性
node.id, node.type, node.page_number, node.level
```

## TableNode 方法

```python
from code_executor.document.models.nodes import TableNode

node.to_text(max_rows=8)          # 格式化文本（喂 LLM）
node.row(i)                       # 第 i 行各列文本
node.col(i)                       # 第 i 列各行文本
node.cell_at(row, col)            # 获取单元格
node.iter_rows(start, end)        # 按行迭代
node.row_num, node.col_num        # 行列数
```

## 工具系统

```python
from code_executor.document.models.document import Document
from code_executor.tools import ToolHub

def extract(document: Document, tool_hub: ToolHub):
    extract_tool = tool_hub.get_tool('extract')      # LLM 结构化提取
    llm_select = tool_hub.get_tool('llm_select')      # LLM 段落筛选
    ...
```

### extract 工具

```python
from pydantic import BaseModel, Field

class InfoSchema(BaseModel):
    company_name: str | None = Field(description="公司名称")
    amount: float | None = Field(description="金额")

result = extract_tool(text_content, schema=InfoSchema)
```

### llm_select 工具

```python
all_texts = document.get_all_texts()
indices = llm_select(all_texts, target="合同签订日期")
chosen = "\\n".join(all_texts[i] for i in indices)
```
""")


@cli.command()
@click.argument("doc_id")
@click.option("--data-dir", type=click.Path(), help="数据目录 (默认 .xdev)")
def standard(doc_id, data_dir):
    """查看文档的标注数据"""
    from .api import get_label, get_label_path
    import json

    label_path = get_label_path(doc_id, data_dir)

    if not label_path.exists():
        click.echo(f"错误：文档 {doc_id} 尚未标注", err=True)
        click.echo(f"标注文件路径: {label_path}")
        raise click.Abort()

    label = get_label(doc_id, data_dir)

    click.echo(f"# 文档 {doc_id} 的标注数据\n")
    click.echo(json.dumps(label, indent=2, ensure_ascii=False))


@cli.command(name="docjson-paths")
@click.option("--data-dir", type=click.Path(), help="数据目录 (默认 .xdev)")
def docjson_paths(data_dir):
    """批量输出 doc_id → docjson 路径映射"""
    from .api import list_doc_ids, get_docjson_path

    doc_ids = list_doc_ids(data_dir)

    for doc_id in doc_ids:
        docjson_path = get_docjson_path(doc_id, data_dir)
        click.echo(f"{doc_id}\t{docjson_path}")


if __name__ == "__main__":
    cli()
