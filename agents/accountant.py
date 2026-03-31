"""会计 Agent，负责记账。

Accountant 是执行记账的 Agent：
1. 用 Skill 理解记账需求
2. 调用 Skill 脚本执行记账
3. 记录反馈到记忆
"""

from agents.base import BaseAgent
from core.skill_loader import SkillLoader


class Accountant(BaseAgent):
    """会计 Agent。

    职责：
    - 根据记账请求执行记账操作
    - 检测异常情况
    - 根据审核反馈修正错误

    Attributes:
        NAME: Agent 名称
        SYSTEM_PROMPT: 从 Skill 加载
    """

    NAME = "accountant"

    def __init__(self):
        """初始化时从 Skill 加载 SYSTEM_PROMPT"""
        try:
            skill = SkillLoader.load(self.NAME)
            self.SYSTEM_PROMPT = skill["system_prompt"]
        except FileNotFoundError:
            self.SYSTEM_PROMPT = "你是财务会计，负责执行记账操作。"

    def process(self, task: str) -> str:
        """处理记账任务。

        调用 Skill 脚本执行记账。

        Args:
            task: 记账任务描述，如"报销1000元差旅费"

        Returns:
            记账结果字符串
        """
        result = SkillLoader.execute_script(
            self.NAME,
            "execute",
            [task, "--json"],
        )

        if result.get("status") == "ok":
            return result.get("message", str(result))

        return f"执行失败: {result.get('message')}"

    def reflect(self, feedback: str) -> None:
        """反思审核反馈，记录到记忆。

        Args:
            feedback: 审核反馈意见
        """
        if feedback:
            self.update_memory(f"审核反馈: {feedback[:200]}")
