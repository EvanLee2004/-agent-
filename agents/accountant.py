"""Accountant Agent"""

import asyncio
import re
from datetime import datetime
from typing import Optional

from agents.base import AsyncAgent
from core.ledger import write_entry
from core.llm import LLMClient
from core.memory import read_memory, write_memory
from core.skill_loader import SkillLoader
from core.message_bus import Message


class Accountant(AsyncAgent):
    """会计 Agent"""

    def __init__(self, bus=None):
        super().__init__("accountant", bus)
        self.skill_name = "accounting"  # Skill 目录名
        try:
            skill = SkillLoader.load(self.skill_name)
            self.SYSTEM_PROMPT = skill["system_prompt"]
        except FileNotFoundError:
            self.SYSTEM_PROMPT = "你是记账专家"

    async def handle(self, msg: Message):
        """处理记账任务"""
        parts = msg.content.split("|")
        task = parts[0]
        feedback = parts[1] if len(parts) > 1 else ""

        result = await asyncio.to_thread(self._process, task, feedback)
        await self.reply(msg, result)

    def _process(self, task: str, feedback: str = "") -> str:
        """同步处理记账"""
        args = [task, "--json"]
        if feedback:
            args.extend(["--feedback", feedback])

        result = SkillLoader.execute_script(self.skill_name, "execute", args)
        if result.get("status") != "ok":
            return f"执行失败: {result.get('message')}"

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
        resp = re.sub(r"<think>.*?</think>", "", resp, flags=re.DOTALL).strip()
        parsed = self._parse(resp)
        if parsed["status"] == "error":
            return f"执行失败: {parsed['message']}"

        if parsed.get("description"):
            parsed["description"] = re.sub(
                r"[,，.。\s]*日期[：:]\d{4}-\d{2}-\d{2}[,，.。\s]*",
                "",
                parsed["description"],
            ).strip()
            parsed["description"] = re.sub(
                r"[,，.。]+$", "", parsed["description"]
            ).strip()

        try:
            dt = parsed.get("date") or datetime.now().strftime("%Y-%m-%d")
            datetime_str = dt + " " + datetime.now().strftime("%H:%M:%S")
            entry_id = write_entry(
                datetime=datetime_str,
                type_=parsed["type"],
                amount=float(parsed["amount"]),
                description=parsed["description"],
                recorded_by=self.name,
                anomaly_flag=parsed["anomaly"].get("flag"),
                anomaly_reason=parsed["anomaly"].get("reason"),
            )
        except Exception as e:
            return f"数据库写入失败: {e}"

        msg = f"[ID:{entry_id}] {parsed['type']} {parsed['amount']}元"
        if parsed.get("date"):
            msg += f", 日期:{parsed['date']}"
        if parsed["description"]:
            msg += f" - {parsed['description']}"

        if feedback:
            self._update_memory(feedback)

        return msg

    def _parse(self, response: str) -> dict:
        """解析 LLM 响应"""
        date_match = re.search(r"日期[:：]?\s*(\d{4}-\d{2}-\d{2})", response)
        date = date_match.group(1) if date_match else None

        amount_match = re.search(r"金额[:：]?\s*(\d+(?:\.\d+)?)", response)
        amount = float(amount_match.group(1)) if amount_match else None

        if "支出" in response:
            type_ = "支出"
        elif "收入" in response:
            type_ = "收入"
        elif "转账" in response:
            type_ = "转账"
        else:
            type_ = None

        desc_match = re.search(r"说明[:：]?\s*(.+?)(?:\n|$)", response)
        description = desc_match.group(1).strip() if desc_match else None

        if not amount or not type_:
            return {"status": "error", "message": f"无法理解：{response}"}

        anomaly = {"flag": None, "reason": None}
        if amount < 10:
            anomaly = {"flag": "high", "reason": f"金额过小: {amount}元"}
        elif amount > 100000:
            anomaly = {"flag": "high", "reason": f"金额过大: {amount}元"}
        elif amount > 50000:
            anomaly = {"flag": "medium", "reason": f"金额较大: {amount}元，需确认"}

        return {
            "status": "ok",
            "date": date,
            "amount": amount,
            "type": type_,
            "description": description,
            "anomaly": anomaly,
        }

    def _update_memory(self, feedback: str):
        """更新记忆"""
        memory = read_memory(self.name)
        memory["experiences"].append(
            {
                "context": f"审核反馈: {feedback[:200]}",
                "learned_at": datetime.now().strftime("%Y-%m-%d"),
            }
        )
        write_memory(self.name, memory)
