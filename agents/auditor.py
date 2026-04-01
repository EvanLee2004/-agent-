"""审计 Agent - 审核记账结果，拥有封驳权"""

import asyncio
import re
from typing import Optional

from agents.base import AsyncAgent
from infrastructure.llm import LLMClient
from infrastructure.ledger import update_entry_status
from infrastructure.skill_loader import SkillLoader
from infrastructure.message_bus import Message


class Auditor(AsyncAgent):
    """审计 - 审核记账结果

    职责：
    - 审核会计的执行结果
    - 合格：准奏（返回"通过"）
    - 不合格：封驳（直接发给会计，不需要经过财务主管）
    - 标注问题，让对方主动修改
    """

    def __init__(self, bus=None):
        super().__init__("审计", bus)
        self.skill_name = "audit"
        try:
            skill = SkillLoader.load(self.skill_name)
            self.SYSTEM_PROMPT = skill["system_prompt"]
        except FileNotFoundError:
            self.SYSTEM_PROMPT = "你是财务审核，负责审查记账结果"

    async def handle(self, msg: Message):
        """处理审核任务"""
        result = await asyncio.to_thread(self._process, msg.content)

        # 判断是准奏还是封驳
        if result.startswith("审核通过"):
            # 准奏，回复给财务主管
            await self.reply(msg, "准奏: " + result, msg_type="approval")
        else:
            # 封驳
            await self.reply(msg, result, msg_type="rejection")

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
        resp = re.sub(r"<extra_thought_token>.*?</extra_thought_token>", "", resp, flags=re.DOTALL).strip()

        if "通过" in resp and "不" not in resp:
            # 审核通过，提取 entry_id 并更新状态
            entry_id = self._extract_entry_id(record)
            if entry_id:
                update_entry_status(entry_id, "approved")
            return "审核通过"

        return resp

    def _extract_entry_id(self, record: str) -> Optional[int]:
        """从记账记录中提取 ID"""
        match = re.search(r"\[ID:(\d+)\]", record)
        return int(match.group(1)) if match else None
