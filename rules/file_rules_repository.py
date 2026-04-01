"""文件规则仓储实现。"""

from conversation.file_prompt_skill_repository import FilePromptSkillRepository
from rules.rules_repository import RulesRepository


class FileRulesRepository(RulesRepository):
    """文件规则仓储实现。"""

    def __init__(self, prompt_skill_repository: FilePromptSkillRepository):
        self._prompt_skill_repository = prompt_skill_repository

    def load_rules_text(self) -> str:
        """读取规则文本。"""
        return self._prompt_skill_repository.load_system_prompt("rules") or "暂无规则说明"
