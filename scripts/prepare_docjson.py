"""
批量将 PDF 转换为 DocJSON

用法:
    uv run python scripts/prepare_docjson.py /path/to/pdf_dir

说明:
    遍历指定目录下的所有 .pdf 文件，调用 memect_apiserver 解析为 docjson，
    输出到同目录下的 docjson/ 子目录。利用 memect_apiserver 内置的 MD5 缓存，
    已解析过的 PDF 不会重复调用 API。
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="批量将 PDF 转换为 DocJSON")
    parser.add_argument("pdf_dir", help="包含 PDF 文件的目录")
    parser.add_argument(
        "--base-url",
        default="http://localhost:6111/api",
        help="apiserver 地址（默认 http://localhost:6111/api）",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="docjson 缓存目录（默认 /tmp/memect_apiserver/cache/）",
    )
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    if not pdf_dir.is_dir():
        print(f"错误: {pdf_dir} 不是有效目录", file=sys.stderr)
        sys.exit(1)

    # 设置缓存目录
    if args.cache_dir:
        from memect_apiserver.parse import set_cache_dir
        set_cache_dir(args.cache_dir)

    # 收集 PDF 文件
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"错误: {pdf_dir} 下没有 PDF 文件", file=sys.stderr)
        sys.exit(1)

    # 创建输出目录
    output_dir = pdf_dir / "docjson"
    output_dir.mkdir(exist_ok=True)

    print(f"PDF 目录: {pdf_dir}")
    print(f"输出目录: {output_dir}")
    print(f"PDF 数量: {len(pdf_files)}")
    print(f"API 地址: {args.base_url}")
    print("-" * 50)

    from memect_apiserver.parse import get_docjson
    import json

    success_count = 0
    fail_count = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        stem = pdf_path.stem  # hex id
        output_path = output_dir / f"{stem}.json"

        # 跳过已存在的
        if output_path.exists():
            print(f"[{i}/{len(pdf_files)}] {stem} 已存在，跳过")
            success_count += 1
            continue

        print(f"[{i}/{len(pdf_files)}] {stem} 解析中...", end=" ", flush=True)
        try:
            pdf_bytes = pdf_path.read_bytes()
            docjson = get_docjson(pdf_bytes, base_url=args.base_url)
            output_path.write_text(
                json.dumps(docjson, ensure_ascii=False), encoding="utf-8"
            )
            print("✓")
            success_count += 1
        except Exception as e:
            print(f"✗ {e}")
            fail_count += 1

    print("-" * 50)
    print(f"完成: {success_count} 成功, {fail_count} 失败")


if __name__ == "__main__":
    main()
