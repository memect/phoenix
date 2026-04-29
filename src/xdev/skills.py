"""Skills 导出功能"""

import zipfile
from pathlib import Path
from importlib import resources

# 导出给外部 coding agent 的 skills（排除 agentic-extract 内部使用的 business/extract_dev）
EXPORT_SKILLS = {
    "xdev",
    "pdf_ai_explorer",
    "extract_workflow",
    "fact-extract",
    "release_process",
}


def export_skills(output_path: Path) -> None:
    """导出 skills 到 ZIP 文件

    Args:
        output_path: 输出 ZIP 文件路径
    """
    # 获取 agentic_extract.skills 目录
    try:
        skills_root = resources.files("agentic_extract") / "skills"
    except Exception as e:
        raise RuntimeError(f"无法找到 skills 目录: {e}")

    # 创建 ZIP 文件
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # 只导出 EXPORT_SKILLS 中的 skill
        for skill_dir in skills_root.iterdir():
            if not skill_dir.is_dir():
                continue
            if skill_dir.name not in EXPORT_SKILLS:
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            # 写入 ZIP（保持目录结构）
            arcname = f"{skill_dir.name}/SKILL.md"
            zf.writestr(arcname, skill_md.read_text(encoding="utf-8"))

    print(f"✓ Skills 已导出到: {output_path}")



def get_default_output_filename() -> str:
    """获取默认输出文件名（带版本号）"""
    try:
        from agentic_extract import __version__
        return f"extract-skills-{__version__}.zip"
    except ImportError:
        return "extract-skills.zip"
