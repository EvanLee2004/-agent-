"""审核 Agent，负责审查记账结果。

Auditor 是审核记账的 Agent：
1. 用 Skill 理解记账结果
2. 调用 Skill 脚本执行审核
3. 返回审核结果
"""

import os

from agents.base import BaseAgent
from core.skill_loader import SkillLoader


class Auditor(BaseAgent):
    """审核 Agent。

    职责：
    - 审查会计的记账结果是否符合规则
    - 发现问题时标注，让会计主动修改

    Attributes:
        NAME: Agent 名称
        SYSTEM_PROMPT: 从 Skill 加载
    """

    NAME = "audit"

    def __init__(self):
        """初始化时从 Skill 加载 SYSTEM_PROMPT"""
        try:
            skill = SkillLoader.load(self.NAME)
            self.SYSTEM_PROMPT = skill["system_prompt"]
        except FileNotFoundError:
            self.SYSTEM_PROMPT = "你是财务审核，负责审查记账结果是否符合规则。"

    def process(self, task: str) -> str:
        """处理审核任务。

        调用 Skill 脚本执行审核。

        Args:
            task: 待审核的记账记录

        Returns:
            审核结果字符串
        """
        result = SkillLoader.execute_script(
            "audit",
            "execute",
            [task, "--json"],
            env={"LLM_API_KEY": os.environ.get("LLM_API_KEY", "")},
        )

        if result.get("status") == "ok":
            return result.get("message", str(result))

        return f"审核失败: {result.get('message')}"
