"""Prompt Skill 仓储接口。"""

from abc import ABC, abstractmethod
from typing import Optional


class PromptSkillRepository(ABC):
    """Prompt Skill 仓储接口。"""

    @abstractmethod
    def load_system_prompt(self, skill_name: str) -> Optional[str]:
        """读取 skill 的系统提示词。

        Args:
            skill_name: skill 名称。

        Returns:
            system prompt 文本；不存在时返回 `None`。
        """
        raise NotImplementedError
