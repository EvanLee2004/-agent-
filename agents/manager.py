"""Manager Agent - 协调者，负责意图分类和流程协调"""

import asyncio
import re
from core.ledger import get_entries
from core.llm import LLMClient
from core.skill_loader import SkillLoader
from agents.base import AsyncAgent
from core.message_bus import Message


class Manager(AsyncAgent):
    """经理 Agent，唯一和用户交互"""

    def __init__(self, bus=None):
        super().__init__("manager", bus)
        self.skill_name = "coordination"
        try:
            skill = SkillLoader.load(self.skill_name)
        except FileNotFoundError:
            self.SYSTEM_PROMPT = "你是财务部门经理"

    async def handle(self, msg: Message):
        """处理用户消息"""
        intent = await self._classify(msg.content)

        if intent == "accounting":
            result = await self._do_accounting(msg.content)
        elif intent == "review":
            result = self._do_review()
        elif intent == "transfer":
            result = await self._do_transfer(msg.content)
        else:
            result = "🤔 无法理解您的意图"

        await self.reply(msg, result)

    async def _classify(self, task: str) -> str:
        """意图分类"""
        result = SkillLoader.execute_script(self.skill_name, "intent", [task, "--json"])
        if result.get("status") != "ok":
            return "unknown"

        data = result.get("data", {})
        messages = [
            {"role": "system", "content": data.get("system", "")},
            {"role": "user", "content": data.get("prompt", "")},
        ]

        try:
            response = await asyncio.to_thread(
                lambda: LLMClient.get_instance().chat(messages)
            )
            resp = response.content
            resp = re.sub(r"<think>.*?</think>", "", resp, flags=re.DOTALL).strip()
            resp_lower = resp.lower()
            resp_num = resp_lower.split(".")[0].strip()

            if resp_num == "2":
                return "review"
            elif resp_num == "3":
                return "transfer"
            elif resp_num == "1" or "记账" in resp_lower or "报销" in resp_lower:
                return "accounting"
        except Exception:
            pass
        return "unknown"

    async def _do_accounting(self, task: str) -> str:
        """处理记账"""
        max_rounds = 2
        feedback = ""

        for i in range(max_rounds):
            acct_reply = await self.send_to("accountant", f"{task}|{feedback}")
            if not acct_reply:
                return f"⚠️ 第 {i + 1} 轮：Accountant 无响应"

            audit_reply = await self.send_to("auditor", acct_reply.content)
            if not audit_reply:
                return f"⚠️ 第 {i + 1} 轮：Auditor 无响应"

            if "通过" in audit_reply.content:
                return f"✅ {acct_reply.content}"

            fb = re.search(r"请补充([^。\n]*)", audit_reply.content)
            if fb:
                feedback = fb.group(0)
            else:
                return f"✅ {acct_reply.content}"

        return f"⚠️ 经过 {max_rounds} 轮仍有问题，需人工确认\n\n审核意见：{feedback}"

    def _do_review(self) -> str:
        """查看账目"""
        entries = get_entries(limit=50)
        if not entries:
            return "暂无记录"

        lines = [f"{'ID':^3} {'时间':^18} {'类型':^4} {'金额':^10} {'说明':^15}"]
        for e in entries:
            flag = "⚠️" if e.get("anomaly_flag") else ""
            lines.append(
                f"{flag}{e['id']:>2} {e['datetime'][:16]:^18} "
                f"{e['type']:^4} ¥{e['amount']:>8.2f} {e['description'][:12]:<12}"
            )
        return "\n".join(lines)

    async def _do_transfer(self, task: str) -> str:
        """转账"""
        return await self._do_accounting(task)
