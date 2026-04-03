"""文件规则仓储实现。"""

import re
from pathlib import Path

from rules.rules_repository import RulesRepository


RULES_SKILL_FILE = Path(".agent_assets/skills/rules/SKILL.md")
SYSTEM_PROMPT_PATTERN = re.compile(r"## SYSTEM_PROMPT\s*\n(.+?)(?=\n##|\Z)", re.DOTALL)


class FileRulesRepository(RulesRepository):
    """从本地 skill 资产读取规则文本。

    当前项目并没有把规则答案硬编码在 service 里，而是把规则文本作为
    独立资产维护。这样后续在不改 Python 代码的情况下，也能迭代财务规则口径。
    规则资产只服务 `rules` 模块本身，因此不再经过 `conversation/` 中转。
    """

    def load_rules_text(self) -> str:
        """读取规则文本。

        Returns:
            `rules` skill 中的规则文本；文件不存在时返回兜底说明。
        """
        if not RULES_SKILL_FILE.exists():
            return "暂无规则说明"

        skill_markdown = RULES_SKILL_FILE.read_text(encoding="utf-8")
        prompt_text = self._extract_system_prompt(skill_markdown)
        if prompt_text:
            return prompt_text
        return self._strip_frontmatter(skill_markdown).strip() or "暂无规则说明"

    def _extract_system_prompt(self, skill_markdown: str) -> str:
        """提取 `## SYSTEM_PROMPT` 段落。"""
        matched = SYSTEM_PROMPT_PATTERN.search(skill_markdown)
        if not matched:
            return ""
        return matched.group(1).strip()

    def _strip_frontmatter(self, skill_markdown: str) -> str:
        """移除 Markdown frontmatter。"""
        if not skill_markdown.startswith("---"):
            return skill_markdown
        parts = skill_markdown.split("---", 2)
        if len(parts) < 3:
            return skill_markdown
        return parts[2]
