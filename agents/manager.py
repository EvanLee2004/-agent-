"""财务主管 Agent - 协调任务流程，分发任务，汇总结果"""

import asyncio
import re
from typing import Optional

from agents.base import AsyncAgent
from core.ledger import get_entries
from core.message_bus import Message


class FinanceManager(AsyncAgent):
    """财务主管 - 任务协调中心

    职责：
    - 接收财务专员转发的任务
    - 分发给会计执行
    - 协调审核流程（循环）
    - 汇总结果返回给财务专员
    """

    def __init__(self, bus=None):
        super().__init__("财务主管", bus)
        self._max_rounds = 2  # 最大协调轮数

    async def handle(self, msg: Message):
        """处理任务消息"""
        intent = msg.intent
        content = msg.content

        if intent == "accounting":
            result = await self._handle_accounting(content, msg)
        elif intent == "transfer":
            result = await self._handle_transfer(content, msg)
        elif intent == "review":
            result = self._handle_review()
        else:
            result = "🤔 无法处理此类型任务"

        await self.reply(msg, result, msg_type="result")

    async def _handle_accounting(self, task: str, original_msg: Message) -> str:
        """处理记账任务"""
        feedback = ""

        for round_num in range(self._max_rounds):
            # 发给会计执行
            # 使用 \t 分隔，避免 task 内容中的 | 造成解析错误
            task_content = f"{task}\t{feedback}" if feedback else task
            acct_reply = await self.send_to(
                recipient="会计",
                content=task_content,
                msg_type="task",
                intent="accounting",
                round=round_num,
            )

            if not acct_reply:
                return f"⚠️ 第 {round_num + 1} 轮：会计无响应"

            # 发给审计审核
            audit_reply = await self.send_to(
                recipient="审计",
                content=acct_reply.content,
                msg_type="task",
                intent="audit",
                round=round_num,
            )

            if not audit_reply:
                return f"⚠️ 第 {round_num + 1} 轮：审计无响应"

            # 检查审核结果
            if "通过" in audit_reply.content or "准奏" in audit_reply.content:
                return f"✅ {acct_reply.content}"

            # 提取反馈，准备下一轮
            fb = re.search(r"请补充([^。\n]*)", audit_reply.content)
            if fb:
                feedback = fb.group(1).strip()  # 只取括号内内容
            else:
                # 没有明确反馈，但没通过
                return f"⚠️ 第 {round_num + 1} 轮审核未通过：{audit_reply.content[:100]}"

        return (
            f"⚠️ 经过 {self._max_rounds} 轮仍有问题，需人工确认\n\n审核意见：{feedback}"
        )

    async def _handle_transfer(self, task: str, original_msg: Message) -> str:
        """处理转账任务（暂同记账）"""
        return await self._handle_accounting(task, original_msg)

    def _handle_review(self) -> str:
        """处理查询请求"""
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
