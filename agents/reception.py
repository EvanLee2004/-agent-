"""财务专员 Agent - 理解用户意图，分类任务，处理闲聊"""

import asyncio
import re
from typing import Optional

from agents.base import AsyncAgent
from core.llm import LLMClient
from core.skill_loader import SkillLoader
from core.message_bus import Message


class Receptionist(AsyncAgent):
    """财务专员 - 用户交互入口

    职责：
    - 理解用户意图（记账/转账/查询/闲聊）
    - 构造标准任务消息
    - 直接回复闲聊
    - 转发任务给财务主管
    """

    def __init__(self, bus=None):
        super().__init__("财务专员", bus)
        self.skill_name = "coordination"
        try:
            skill = SkillLoader.load(self.skill_name)
        except FileNotFoundError:
            self.SYSTEM_PROMPT = "你是财务专员，负责理解用户意图"

    async def handle(self, msg: Message):
        """处理用户消息"""
        content = msg.content.strip()

        # 判断是否是闲聊
        intent = await self._classify_intent(content)

        if intent == "chat":
            # 闲聊直接回复
            response = await self._handle_chat(content)
            await self.reply(msg, response, msg_type="chat")
        elif intent in ("accounting", "transfer", "review"):
            # 任务消息，转发给财务主管
            task_msg = self._construct_task(content, intent)
            reply = await self.send_to(
                recipient="财务主管",
                content=task_msg,
                msg_type="task",
                intent=intent,
            )
            if reply:
                await self.reply(msg, reply.content, msg_type="result")
            else:
                await self.reply(msg, "⚠️ 系统繁忙，请稍后重试", msg_type="error")
        else:
            await self.reply(
                msg,
                "🤔 我不太理解您的意思，您可以：\n- 报销/收入/支出：记账\n- 查看账目：查询\n- 转账：转账",
                msg_type="chat",
            )

    async def _classify_intent(self, content: str) -> str:
        """意图分类"""
        # 简单规则 + LLM 辅助
        content_lower = content.lower()

        # 简单规则优先
        if any(kw in content_lower for kw in ["查看", "账目", "账单", "记录", "查询"]):
            return "review"
        if any(kw in content_lower for kw in ["转账", "汇款"]):
            return "transfer"
        if any(
            kw in content_lower
            for kw in ["报销", "收入", "支出", "付", "收", "货款", "回款"]
        ):
            return "accounting"

        # 使用 LLM 辅助判断
        return await self._classify_with_llm(content)

    async def _classify_with_llm(self, content: str) -> str:
        """使用 LLM 进行意图分类"""
        result = SkillLoader.execute_script(
            self.skill_name, "intent", [content, "--json"]
        )
        if result.get("status") != "ok":
            return "chat"

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
            elif (
                resp_num == "1"
                or "记账" in resp_lower
                or "报销" in resp_lower
                or "收入" in resp_lower
                or "支出" in resp_lower
            ):
                return "accounting"
        except Exception:
            pass

        return "chat"

    def _construct_task(self, content: str, intent: str) -> str:
        """构造标准任务消息"""
        return f"[{intent}] {content}"

    async def _handle_chat(self, content: str) -> str:
        """处理闲聊"""
        # 简单的闲聊回复
        greetings = ["你好", "您好", "hi", "hello", "嗨"]
        content_lower = content.lower()

        if any(g in content_lower for g in greetings):
            return "您好！我是财务专员，请问有什么可以帮您？\n- 报销/收入/支出：记账\n- 查看账目：查询\n- 转账：转账"

        if "谢谢" in content:
            return "不客气！还有其他财务问题吗？"

        if "再见" in content or "退出" in content:
            return "再见！有需要随时找我。"

        return "我理解您的意思，但作为财务专员，我主要处理：\n- 记账（报销、收入、支出）\n- 查询账目\n- 转账\n\n请告诉我您需要哪项服务？"
