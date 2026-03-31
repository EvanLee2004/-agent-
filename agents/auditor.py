"""审核 Agent，负责审查记账结果。

Auditor 是审核记账的 Agent：
1. 调用 Skill 获取 prompt
2. 用 LLM 统一处理
3. 返回审核结果
"""

import re

from agents.base import BaseAgent
from core.llm import LLMClient
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

        调用 Skill 获取 prompt，然后用 LLM 统一处理。

        Args:
            task: 待审核的记账记录

        Returns:
            审核结果字符串
        """
        result = SkillLoader.execute_script(
            "audit",
            "execute",
            [task, "--json"],
        )

        if result.get("status") != "ok":
            return f"审核失败: {result.get('message')}"

        data = result.get("data")
        if not data:
            return f"审核失败: {result.get('message')}"

        messages = [
            {"role": "system", "content": data.get("system", "")},
            {"role": "user", "content": data.get("prompt", "")},
        ]

        try:
            llm_response = LLMClient.get_instance().chat(messages)
        except Exception as e:
            return f"LLM 调用失败: {str(e)}"

        return self._parse_audit_response(llm_response)

    @staticmethod
    def _parse_audit_response(response: str) -> str:
        """从 LLM 响应中解析审核结果。

        Args:
            response: LLM 返回的文本

        Returns:
            审核结果字符串
        """
        if "通过" in response and "不" not in response:
            return "审核通过"

        return response
