"""Auditor Agent"""

import asyncio

from agents.base import AsyncAgent
from core.llm import LLMClient
from core.skill_loader import SkillLoader
from core.message_bus import Message


class Auditor(AsyncAgent):
    """审核 Agent"""

    def __init__(self, bus=None):
        super().__init__("auditor", bus)
        self.skill_name = "audit"  # Skill 目录名
        try:
            skill = SkillLoader.load(self.skill_name)
            self.SYSTEM_PROMPT = skill["system_prompt"]
        except FileNotFoundError:
            self.SYSTEM_PROMPT = "你是财务审核"

    async def handle(self, msg: Message):
        """处理审核任务"""
        result = await asyncio.to_thread(self._process, msg.content)
        await self.reply(msg, result)

    def _process(self, record: str) -> str:
        """同步处理审核"""
        result = SkillLoader.execute_script(
            self.skill_name, "execute", [record, "--json"]
        )
        if result.get("status") != "ok":
            return f"审核失败: {result.get('message')}"

        data = result.get("data", {})
        messages = [
            {"role": "system", "content": data.get("system", "")},
            {"role": "user", "content": data.get("prompt", "")},
        ]

        try:
            llm_response = LLMClient.get_instance().chat(messages)
        except Exception as e:
            return f"LLM 调用失败: {e}"

        resp = llm_response.content
        import re

        resp = re.sub(r"<think>.*?</think>", "", resp, flags=re.DOTALL).strip()
        if "通过" in resp and "不" not in resp:
            return "审核通过"
        return resp
