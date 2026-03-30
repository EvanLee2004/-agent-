"""规则读取模块，供会计和审核使用"""

from pathlib import Path


def read_rules(filename: str = "accounting_rules.md") -> str:
    """读取规则文件"""
    path = Path("rules") / filename
    if path.exists():
        return path.read_text()
    return ""
