"""
Code Executor CLI 模块

提供命令行接口。
"""

import typer
import json
import asyncio
from pathlib import Path
from typing import Optional

app = typer.Typer(help="代码执行工具")


@app.command("run")
def run(
    program: str = typer.Option(..., "--program", "-p", help="程序文件路径"),
    input_file: str = typer.Option(..., "--input", "-i", help="输入 DocJSON 文件"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="输出文件路径"),
):
    """执行单个文档的提取"""
    from .executor import execute
    
    # 读取程序文件
    program_path = Path(program)
    if not program_path.exists():
        typer.echo(f"错误: 程序文件不存在: {program}", err=True)
        raise typer.Exit(1)
    
    program_code = program_path.read_text(encoding="utf-8")
    
    # 读取输入文件
    input_path = Path(input_file)
    if not input_path.exists():
        typer.echo(f"错误: 输入文件不存在: {input_file}", err=True)
        raise typer.Exit(1)
    
    with open(input_path, "r", encoding="utf-8") as f:
        docjson = json.load(f)
    
    # 执行提取（自动检测输入模式）
    try:
        result = asyncio.run(execute(program=program_code, docjson=docjson))
    except ValueError as e:
        typer.echo(f"错误: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"执行错误: {e}", err=True)
        raise typer.Exit(1)
    
    # 输出结果
    result_json = json.dumps(result, ensure_ascii=False, indent=2)
    
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result_json, encoding="utf-8")
        typer.echo(f"结果已保存到: {output}")
    else:
        typer.echo(result_json)


@app.command("batch")
def batch(
    program: str = typer.Option(..., "--program", "-p", help="程序文件路径"),
    input_dir: str = typer.Option(..., "--input-dir", "-i", help="输入目录"),
    output_dir: str = typer.Option(..., "--output-dir", "-o", help="输出目录"),
    concurrent: int = typer.Option(5, "--concurrent", "-c", help="并发数"),
):
    """批量执行提取"""
    from .api import batch_execute_on_docjsons
    
    # 读取程序文件
    program_path = Path(program)
    if not program_path.exists():
        typer.echo(f"错误: 程序文件不存在: {program}", err=True)
        raise typer.Exit(1)
    
    program_code = program_path.read_text(encoding="utf-8")
    
    # 读取输入目录中的所有 JSON 文件
    input_path = Path(input_dir)
    if not input_path.exists():
        typer.echo(f"错误: 输入目录不存在: {input_dir}", err=True)
        raise typer.Exit(1)
    
    json_files = list(input_path.glob("*.json"))
    if not json_files:
        typer.echo(f"警告: 输入目录中没有 JSON 文件: {input_dir}")
        raise typer.Exit(0)
    
    typer.echo(f"找到 {len(json_files)} 个 JSON 文件")
    
    # 读取所有 DocJSON 文件
    docjsons = []
    file_names = []
    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                docjson = json.load(f)
            docjsons.append(docjson)
            file_names.append(json_file.stem)
        except Exception as e:
            typer.echo(f"警告: 无法读取文件 {json_file}: {e}")
    
    if not docjsons:
        typer.echo("错误: 没有有效的输入文件")
        raise typer.Exit(1)
    
    # 批量执行
    typer.echo(f"开始批量执行，并发数: {concurrent}")
    results = asyncio.run(batch_execute_on_docjsons(program_code, docjsons, concurrent))
    
    # 保存结果
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    success_count = 0
    error_count = 0
    
    for result, file_name in zip(results, file_names):
        output_file = output_path / f"{file_name}.json"
        
        if result['success']:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result['data'], f, ensure_ascii=False, indent=2)
            success_count += 1
        else:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({'error': result['error']}, f, ensure_ascii=False, indent=2)
            error_count += 1
    
    typer.echo(f"完成: 成功 {success_count}, 失败 {error_count}")
    typer.echo(f"结果已保存到: {output_dir}")


if __name__ == "__main__":
    app()
