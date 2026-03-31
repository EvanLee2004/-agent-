"""会计 Agent，负责记账。

Accountant 是执行记账的 Agent：
1. 用 LLM 理解记账需求
2. 写入数据库
3. 记录反馈到记忆
"""

from datetime import datetime
from typing import Any, Optional

from agents.base import BaseAgent
from core.ledger import write_entry
from core.rules import read_rules


class Accountant(BaseAgent):
    """会计 Agent。

    职责：
    - 根据记账请求执行记账操作
    - 检测异常情况
    - 根据审核反馈修正错误

    Attributes:
        NAME: Agent 名称
        SYSTEM_PROMPT: 系统提示词
    """

    NAME = "accountant"
    SYSTEM_PROMPT = (
        "你是财务会计，负责根据记账守则执行记账操作。\n规则：\n" + read_rules()
    )

    def process(self, task: str) -> str:
        """处理记账任务。

        用 LLM 理解任务，提取记账信息，写入数据库。

        Args:
            task: 记账任务描述，如"报销1000元差旅费"

        Returns:
            记账结果字符串
        """
        rules = read_rules()

        prompt = (
            f"从以下任务中提取记账信息，直接回答：\n"
            f"任务：{task}\n\n"
            f"提取：金额（数字）、类型（收入/支出/转账）、说明\n"
            f"规则：\n{rules}\n\n"
            f"回答格式：金额:xxx, 类型:xxx, 说明:xxx"
        )

        response = self.ask_llm(prompt)

        amount, type_, description = self._parse_response(response)

        if not amount or not type_:
            return f"无法理解记账信息：{response}"

        anomaly = self._detect_anomaly(amount, type_ or "", description or "")

        entry_id = write_entry(
            datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            type_=type_,
            amount=float(amount),
            description=description or f"{type_} {amount}元",
            recorded_by=self.NAME,
            anomaly_flag=anomaly.get("flag"),
            anomaly_reason=anomaly.get("reason"),
        )

        result = f"[ID:{entry_id}] {type_} {amount}元"
        if description:
            result += f" - {description}"
        if anomaly.get("flag"):
            result += f" ⚠️ 异常: {anomaly['reason']}"

        return result

    def reflect(self, feedback: str) -> None:
        """反思审核反馈，记录到记忆。

        Args:
            feedback: 审核反馈意见
        """
        if feedback:
            self.update_memory(f"审核反馈: {feedback[:200]}")

    def _parse_response(
        self,
        response: str,
    ) -> tuple[Optional[float], Optional[str], Optional[str]]:
        """从 LLM 响应中解析记账信息。

        用简单规则匹配，而非 JSON 解析。

        Args:
            response: LLM 返回的文本

        Returns:
            (amount, type_, description) 元组
        """
        import re

        amount = None
        type_ = None
        description = None

        amount_match = re.search(r"金额[:：]?\s*(\d+(?:\.\d+)?)", response)
        if amount_match:
            amount = float(amount_match.group(1))

        if "支出" in response:
            type_ = "支出"
        elif "收入" in response:
            type_ = "收入"
        elif "转账" in response:
            type_ = "转账"

        desc_match = re.search(r"说明[:：]?\s*(.+?)(?:\n|$)", response)
        if desc_match:
            description = desc_match.group(1).strip()

        return amount, type_, description

    def _detect_anomaly(
        self,
        amount: Optional[float],
        type_: str,
        description: str,
    ) -> dict[str, Any]:
        """检测记账异常。

        根据金额大小、类型等判断是否有异常。

        Args:
            amount: 金额
            type_: 类型（收入/支出/转账）
            description: 描述

        Returns:
            dict: {"flag": "high"|"medium"|None, "reason": str}
        """
        anomaly: dict[str, Any] = {"flag": None, "reason": None}

        if amount is None:
            return anomaly

        if amount < 10:
            anomaly["flag"] = "high"
            anomaly["reason"] = f"金额过小: {amount}元"
        elif amount > 100000:
            anomaly["flag"] = "high"
            anomaly["reason"] = f"金额过大: {amount}元"
        elif amount > 50000:
            anomaly["flag"] = "medium"
            anomaly["reason"] = f"金额较大: {amount}元，需确认"

        if "异常" in description or "问题" in description:
            if anomaly["flag"]:
                anomaly["reason"] += f"，另: {description}"
            else:
                anomaly["flag"] = "medium"
                anomaly["reason"] = description

        return anomaly
