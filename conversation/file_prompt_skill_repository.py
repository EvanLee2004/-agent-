"""文件 Prompt Skill 仓储实现。"""

import re
from pathlib import Path
from typing import Optional

from conversation.prompt_skill_repository import PromptSkillRepository


SKILLS_ROOT = Path(".agent_assets/skills")
SYSTEM_PROMPT_PATTERN = re.compile(r"## SYSTEM_PROMPT\s*\n(.+?)(?=\n##|\Z)", re.DOTALL)


class FilePromptSkillRepository(PromptSkillRepository):
    """文件 Prompt Skill 仓储实现。"""

    def load_system_prompt(self, skill_name: str) -> Optional[str]:
        """读取 skill 中的 system prompt。"""
        skill_file = SKILLS_ROOT / skill_name / "SKILL.md"
        if not skill_file.exists():
            return None

        skill_markdown = skill_file.read_text(encoding="utf-8")
        prompt_text = self._extract_system_prompt(skill_markdown)
        if not prompt_text:
            stripped_markdown = self._strip_frontmatter(skill_markdown).strip()
            if stripped_markdown.startswith("#"):
                return stripped_markdown
            return None
        return prompt_text.strip()

    def _extract_system_prompt(self, skill_markdown: str) -> str:
        """提取 `## SYSTEM_PROMPT` 段落。"""
        matched = SYSTEM_PROMPT_PATTERN.search(skill_markdown)
        if not matched:
            return ""
        return matched.group(1).strip()

    def _strip_frontmatter(self, skill_markdown: str) -> str:
        """去掉 frontmatter。"""
        if not skill_markdown.startswith("---"):
            return skill_markdown
        parts = skill_markdown.split("---", 2)
        if len(parts) < 3:
            return skill_markdown
        return parts[2]
