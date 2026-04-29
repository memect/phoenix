"""
一键准备 workspace：生成 docjson + 导入数据 + 写入 schema

用法:
    uv run python scripts/prepare_workspace.py \
        --source-dir "/path/to/pdf-dataset/train" \
        --workspace <workspace_path>

步骤:
    1. 批量 PDF → DocJSON（调用 memect_apiserver）
    2. 导入数据到 workspace/.extract-dev/data/
    3. 写入 schema 到 .extract-dev/schema.json
"""

import argparse
import json
import sys
from pathlib import Path


# 第一类 schema：公司股本结构
SHARE_STRUCTURE_SCHEMA = {
    "type": "object",
    "data": {
        "restricted_other_shares": "str",
        "domestic_restricted_shares": "str",
        "domestic_natural_person_shares": "str",
        "controlling_shareholder_shares": "str",
        "total_restricted_shares": "str",
        "rmb_common_shares": "str",
        "circulating_shares": "str",
        "total_share_capital": "str",
    },
}


def step1_generate_docjson(source_dir: Path, base_url: str, concurrent: int = 3) -> None:
    """步骤 1：批量 PDF → DocJSON（并发）"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from memect_apiserver.parse import get_docjson

    pdf_files = sorted(source_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"错误: {source_dir} 下没有 PDF 文件", file=sys.stderr)
        sys.exit(1)

    output_dir = source_dir / "docjson"
    output_dir.mkdir(exist_ok=True)

    # 过滤已存在的
    todo = []
    for pdf_path in pdf_files:
        output_path = output_dir / f"{pdf_path.stem}.json"
        if output_path.exists():
            print(f"  {pdf_path.stem} 已存在，跳过")
        else:
            todo.append(pdf_path)

    print(f"\n=== 步骤 1: 生成 DocJSON ===")
    print(f"PDF 总数: {len(pdf_files)}, 待处理: {len(todo)}, 并发: {concurrent}")
    print(f"输出目录: {output_dir}")

    if not todo:
        print("  全部已存在，跳过")
        return

    def _process_one(pdf_path: Path) -> tuple[str, bool, str]:
        stem = pdf_path.stem
        output_path = output_dir / f"{stem}.json"
        try:
            pdf_bytes = pdf_path.read_bytes()
            docjson = get_docjson(pdf_bytes, base_url=base_url)
            output_path.write_text(
                json.dumps(docjson, ensure_ascii=False), encoding="utf-8"
            )
            return stem, True, ""
        except Exception as e:
            return stem, False, str(e)

    done = 0
    with ThreadPoolExecutor(max_workers=concurrent) as pool:
        futures = {pool.submit(_process_one, p): p for p in todo}
        for future in as_completed(futures):
            stem, ok, err = future.result()
            done += 1
            status = "✓" if ok else f"✗ {err}"
            print(f"  [{done}/{len(todo)}] {stem} {status}")


def step2_import_data(source_dir: Path, workspace: Path) -> None:
    """步骤 2：导入数据到 workspace"""
    from extract_dev.local_data import import_from_directory

    override_dir = workspace / ".extract-dev"
    print(f"\n=== 步骤 2: 导入数据到 workspace ===")
    print(f"源目录: {source_dir}")
    print(f"目标: {override_dir / 'data'}")

    data_dir = import_from_directory(
        source_dir, override_dir=override_dir,
    )
    print(f"导入完成: {data_dir}")


def step3_write_schema(workspace: Path) -> None:
    """步骤 3：写入 schema"""
    from extract_dev.override import set_schema

    override_dir = workspace / ".extract-dev"
    print(f"\n=== 步骤 3: 写入 schema ===")
    set_schema(SHARE_STRUCTURE_SCHEMA, override_dir=override_dir)
    print(f"schema 已写入: {override_dir / 'schema.json'}")


def main():
    parser = argparse.ArgumentParser(description="一键准备 workspace")
    parser.add_argument("--source-dir", required=True, help="PDF 源目录")
    parser.add_argument("--workspace", required=True, help="workspace 路径")
    parser.add_argument(
        "--base-url",
        default="http://localhost:6111/api",
        help="apiserver 地址",
    )
    parser.add_argument(
        "--skip-docjson", action="store_true",
        help="跳过 docjson 生成（已有时使用）",
    )
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    workspace = Path(args.workspace)

    if not source_dir.is_dir():
        print(f"错误: 源目录不存在: {source_dir}", file=sys.stderr)
        sys.exit(1)

    workspace.mkdir(parents=True, exist_ok=True)

    if not args.skip_docjson:
        step1_generate_docjson(source_dir, args.base_url)

    step2_import_data(source_dir, workspace)
    step3_write_schema(workspace)

    print(f"\n=== 完成 ===")
    print(f"workspace: {workspace}")
    print(f"下一步: uv run agentscope-agent run --unlabeled --workspace {workspace} ...")


if __name__ == "__main__":
    main()
