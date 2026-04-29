"""Workspace 初始化"""

import subprocess
from pathlib import Path
from importlib import resources


def init_workspace(workspace_path: Path) -> None:
    """初始化 workspace 目录结构

    Args:
        workspace_path: workspace 路径
    """
    workspace_path.mkdir(parents=True, exist_ok=True)

    # 初始化 git 仓库
    _init_git(workspace_path)

    # 复制模板文件
    _copy_gitignore(workspace_path)
    _copy_program_template(workspace_path)
    _create_tests_dir(workspace_path)
    _create_docs_dir(workspace_path)
    _create_xdev_dir(workspace_path)

    print(f"✓ Workspace 已初始化: {workspace_path}")


def _init_git(workspace_path: Path) -> None:
    """初始化 git 仓库"""
    git_dir = workspace_path / ".git"
    if git_dir.exists():
        print("  复用已有 .git")
        return

    try:
        subprocess.run(
            ["git", "init"],
            cwd=str(workspace_path),
            check=True,
            capture_output=True,
            text=True,
        )
        print("  创建 .git")
    except Exception as e:
        print(f"  警告: git init 失败: {e}")


def _copy_gitignore(workspace_path: Path) -> None:
    """复制 .gitignore 模板"""
    dst = workspace_path / ".gitignore"
    if dst.exists():
        print("  复用已有 .gitignore")
        return

    # 从 extract_agent_common 读取模板
    try:
        templates_dir = resources.files("extract_agent_common") / "templates"
        src = templates_dir / ".gitignore"
        content = src.read_text(encoding="utf-8")
        dst.write_text(content, encoding="utf-8")
        print("  创建 .gitignore")
    except Exception as e:
        print(f"  警告: 无法复制 .gitignore: {e}")


def _copy_program_template(workspace_path: Path) -> None:
    """复制 program.py 模板"""
    dst = workspace_path / "program.py"
    if dst.exists():
        print("  复用已有 program.py")
        return

    # xdev 强制使用 Document(tree) 模式模板
    try:
        templates_dir = resources.files("extract_agent_common") / "templates"
        src = templates_dir / "tree" / "program.py"
        content = src.read_text(encoding="utf-8")
        dst.write_text(content, encoding="utf-8")
        print("  创建 program.py")
    except Exception as e:
        print(f"  警告: 无法复制 program.py: {e}")


def _create_tests_dir(workspace_path: Path) -> None:
    """创建 tests 目录和模板"""
    tests_dir = workspace_path / "tests"
    tests_dir.mkdir(exist_ok=True)

    # 复制 conftest.py
    conftest = tests_dir / "conftest.py"
    if not conftest.exists():
        try:
            templates_dir = resources.files("extract_agent_common") / "templates"
            src = templates_dir / "tests_tree" / "conftest.py"
            content = src.read_text(encoding="utf-8")
            conftest.write_text(content, encoding="utf-8")
            print("  创建 tests/conftest.py")
        except Exception as e:
            print(f"  警告: 无法复制 conftest.py: {e}")

    # 复制 test_extract.py
    test_extract = tests_dir / "test_extract.py"
    if not test_extract.exists():
        try:
            templates_dir = resources.files("extract_agent_common") / "templates"
            src = templates_dir / "tests_tree" / "test_extract.py"
            content = src.read_text(encoding="utf-8")
            test_extract.write_text(content, encoding="utf-8")
            print("  创建 tests/test_extract.py")
        except Exception as e:
            print(f"  警告: 无法复制 test_extract.py: {e}")


def _create_docs_dir(workspace_path: Path) -> None:
    """创建 docs 目录"""
    docs_dir = workspace_path / "docs"
    existed = docs_dir.exists()
    docs_dir.mkdir(exist_ok=True)
    print("  复用已有 docs/" if existed else "  创建 docs/")


def _create_xdev_dir(workspace_path: Path) -> None:
    """创建 .xdev 空目录"""
    xdev_dir = workspace_path / ".xdev"
    xdev_dir.mkdir(exist_ok=True)

    # 创建子目录
    (xdev_dir / "data" / "docjson").mkdir(parents=True, exist_ok=True)
    (xdev_dir / "data" / "pdf").mkdir(parents=True, exist_ok=True)
    (xdev_dir / "labels").mkdir(exist_ok=True)

    print("  创建 .xdev/")
