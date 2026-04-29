"""pytest 配置"""
import sys
from pathlib import Path

# 添加 workspace 到 path，让 program.py 可被导入
sys.path.insert(0, str(Path(__file__).parent.parent))
