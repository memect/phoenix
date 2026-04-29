"""Workspace 创建与管理"""

import logging
import os
import uuid
import shutil
import subprocess
from importlib import resources
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_templates_dir() -> Path:
    """获取模板目录路径（支持包安装后访问）"""
    # 使用 importlib.resources 获取包内资源路径
    return Path(str(resources.files("extract_agent_common") / "templates"))


def create_workspace(
    workspace: str | None,
    base_dir: str | Path | None = None,
) -> Path:
    """创建或复用工作目录
    
    Args:
        workspace: 工作目录路径，为 None 时自动生成
        base_dir: 自动生成时的父目录（默认 local/workspaces/）
        
    Returns:
        工作目录 Path 对象（绝对路径）
    """
    if workspace:
        workspace_path = Path(workspace).resolve()
    else:
        parent = Path(base_dir) if base_dir else Path("local/workspaces")
        workspace_id = str(uuid.uuid4())[:8]
        workspace_path = (parent / workspace_id).resolve()
    
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    # 初始化 git 仓库
    git_dir = workspace_path / ".git"
    if not git_dir.exists():
        try:
            subprocess.run(
                ["git", "init"],
                cwd=str(workspace_path),
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("初始化 git 仓库: %s", workspace_path)
        except Exception as exc:
            logger.warning("git init 失败: %s", exc)

    logger.info("输入模式: Document")
    
    # 从模板复制文件（仅当目标不存在时）
    _copy_template_file(".gitignore", workspace_path)
    
    # xdev/code_executor 运行时只支持 Document 模式。
    _copy_template_file_with_mode("tree/program.py", workspace_path / "program.py")
    
    # 创建 tests 目录和模板
    tests_path = workspace_path / "tests"
    tests_path.mkdir(exist_ok=True)
    
    _copy_template_file_with_mode(
        "tests_tree/conftest.py",
        workspace_path / "tests" / "conftest.py",
    )
    _copy_template_file_with_mode(
        "tests_tree/test_extract.py",
        workspace_path / "tests" / "test_extract.py",
    )
    
    # 创建 docs 目录
    docs_path = workspace_path / "docs"
    docs_path.mkdir(exist_ok=True)
    
    return workspace_path


def _copy_template_file(relative_path: str, workspace_path: Path) -> None:
    """从模板目录复制文件到工作目录（仅当目标不存在时）
    
    Args:
        relative_path: 相对于模板目录/工作目录的路径
        workspace_path: 工作目录
    """
    templates_dir = _get_templates_dir()
    src = templates_dir / relative_path
    dst = workspace_path / relative_path
    
    if dst.exists():
        logger.info("复用已有 %s", relative_path)
        return

    if not src.exists():
        logger.warning("模板不存在: %s", src)
        return

    shutil.copy2(src, dst)
    logger.info("创建 %s", relative_path)


def _copy_template_file_with_mode(src_relative_path: str, dst_path: Path) -> None:
    """从模板目录复制文件到指定目标路径（支持模式选择）
    
    Args:
        src_relative_path: 相对于模板目录的源文件路径（如 "tree/program.py"）
        dst_path: 目标文件的完整路径
    """
    templates_dir = _get_templates_dir()
    src = templates_dir / src_relative_path
    
    if dst_path.exists():
        rel_path = dst_path.name if dst_path.parent.name == "tests" else dst_path.parent.name + "/" + dst_path.name
        logger.info("复用已有 %s", rel_path)
        return

    if not src.exists():
        logger.warning("模板不存在: %s", src)
        return

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst_path)
    rel_path = dst_path.name if dst_path.parent.name in ["tests", "docs"] else dst_path.relative_to(dst_path.parent.parent)
    logger.info("创建 %s", rel_path)


def setup_environment(
    workspace_path: Path,
    chdir: bool = True,
) -> None:
    """设置环境变量

    Args:
        workspace_path: 工作目录
        chdir: 是否切换到工作目录（默认 True）
    """
    program_path = workspace_path / "program.py"
    os.environ["EXTRACT_PROGRAM"] = str(program_path.absolute())

    if chdir:
        os.chdir(workspace_path.absolute())
        logger.info("工作目录: %s", os.getcwd())

    logger.info("EXTRACT_PROGRAM=%s", os.environ['EXTRACT_PROGRAM'])
