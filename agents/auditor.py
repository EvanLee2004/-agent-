"""Auditor Agent - Reviews and validates accounting records.

The Auditor is responsible for:
1. Loading SYSTEM_PROMPT from the audit Skill
2. Calling the Skill script to get prompt data
3. Invoking LLM via centralized LLMClient to process audit
4. Returning audit results

The audit workflow:
- Accountant creates initial record
- Auditor reviews for rule compliance
- If issues found, Accountant revises based on feedback
- Up to 3 revision cycles before final rejection
"""

import re

from agents.base import BaseAgent
from core.llm import LLMClient
from core.skill_loader import SkillLoader


class Auditor(BaseAgent):
    """Auditor Agent that reviews accounting records for rule compliance.

    The Auditor examines the Accountant's entries against established
    accounting rules and flags any violations or anomalies. When issues
    are detected, the Auditor provides feedback for the Accountant to
    correct and resubmit.

    Attributes:
        NAME: Agent identifier, corresponds to 'audit' Skill directory.
        SYSTEM_PROMPT: System prompt loaded from Skill on initialization.

    Example:
        auditor = Auditor()
        result = auditor.process("收入 5000元 客户付款")
    """

    NAME = "audit"

    def __init__(self):
        """Initialize Auditor by loading SYSTEM_PROMPT from Skill.

        Attempts to load the 'audit' Skill. If the Skill directory or
        SKILL.md is not found, falls back to a default system prompt.
        """
        try:
            skill = SkillLoader.load(self.NAME)
            self.SYSTEM_PROMPT = skill["system_prompt"]
        except FileNotFoundError:
            self.SYSTEM_PROMPT = (
                "You are a financial auditor responsible for reviewing "
                "accounting records for compliance with established rules."
            )

    def process(self, task: str) -> str:
        """Process an audit task for the given accounting record.

        Executes the audit workflow:
        1. Calls the audit Skill script to build prompt data
        2. Sends prompt to LLM via centralized LLMClient
        3. Parses and returns the audit response

        Args:
            task: The accounting record to audit, typically formatted as
                "类型 金额 说明" (e.g., "支出 1000 办公用品").

        Returns:
            Audit result string. Returns "审核通过" (approved) if no
            issues found, otherwise returns the LLM's detailed feedback.
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

        return self._parse_audit_response(llm_response)

    @staticmethod
    def _parse_audit_response(response: str) -> str:
        """Parse the LLM audit response to determine approval status.

        Checks the LLM response text for approval indicators. A response
        containing "通过" (approve/pass) without "不" (not) is considered
        approved.

        Args:
            response: Raw text response from the LLM audit call.

        Returns:
            "审核通过" if the response indicates approval, otherwise
            returns the original LLM response text with feedback.
        """
        if "通过" in response and "不" not in response:
            return "审核通过"

        return response
