"""Auditor Agent - 审核记账结果

Auditor 负责审核记账结果：
1. 从 audit Skill 加载 SYSTEM_PROMPT
2. 调用 Skill 脚本获取 prompt 数据
3. 通过中心化 LLMClient 调用 LLM
4. 返回审核结果

工作流程：
- Accountant 创建初始记账记录
- Auditor 审核是否符合规则
- 如发现问题，提供反馈让 Accountant 修正
- 最多 3 轮修正循环
"""

import re

from agents.base import BaseAgent
from core.llm import LLMClient
from core.skill_loader import SkillLoader


class Auditor(BaseAgent):
    """审核 Agent，审查记账记录是否符合规则。

    Auditor 审查 Accountant 的记账条目是否符合既定规则，
    发现问题时提供反馈让 Accountant 修正后重新提交。

    Attributes:
        NAME: Agent 标识符，对应 'audit' Skill 目录。
        SYSTEM_PROMPT: 初始化时从 Skill 加载的系统提示词。

    Example:
        auditor = Auditor()
        result = auditor.process("收入 5000元 客户付款")
    """

    NAME = "audit"

    def __init__(self):
        """初始化 Auditor，从 Skill 加载 SYSTEM_PROMPT。

        尝试加载 'audit' Skill。如果 Skill 目录或 SKILL.md 不存在，
        则回退到默认系统提示词。
        """
        try:
            skill = SkillLoader.load(self.NAME)
            self.SYSTEM_PROMPT = skill["system_prompt"]
        except FileNotFoundError:
            self.SYSTEM_PROMPT = "你是财务审核，负责审查记账结果是否符合规则。"

    def process(self, task: str) -> str:
        """处理审核任务。

        执行审核工作流程：
        1. 调用 audit Skill 脚本构建 prompt 数据
        2. 通过 LLMClient 发送 prompt 给 LLM
        3. 解析并返回审核响应

        Args:
            task: 待审核的记账记录，格式通常为
                "类型 金额 说明"（如"支出 1000 办公用品"）。

        Returns:
            审核结果字符串。如果没问题返回"审核通过"，
            否则返回 LLM 的详细反馈。
        """
        result = SkillLoader.execute_script(
            "audit",
            "execute",
            [task, "--json"],
        )

        if result.get("status") != "ok":
            return f"Audit failed: {result.get('message')}"

        data = result.get("data")
        if not data:
            return f"Audit failed: {result.get('message')}"

        messages = [
            {"role": "system", "content": data.get("system", "")},
            {"role": "user", "content": data.get("prompt", "")},
        ]

        try:
            llm_response = LLMClient.get_instance().chat(messages)
        except Exception as e:
            return f"LLM call failed: {str(e)}"

        return self._parse_audit_response(llm_response.content)

    @staticmethod
    def _parse_audit_response(response: str) -> str:
        """解析 LLM 审核响应，判断是否通过。

        检查 LLM 响应文本中的审核指示器。如果响应包含"通过"
        且不包含"不"，则认为审核通过。

        Args:
            response: LLM 审核调用的原始文本响应。

        Returns:
            如果响应表示通过则返回"审核通过"，
            否则返回带有反馈的原始 LLM 响应文本。
        """
        if "通过" in response and "不" not in response:
            return "审核通过"

        return response
