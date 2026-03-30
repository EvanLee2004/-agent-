"""会计 Agent，负责记账"""

from datetime import datetime
from typing import Optional

from agents.base import BaseAgent
from core.ledger import write_entry


class Accountant(BaseAgent):
    NAME = "accountant"
    SYSTEM_PROMPT = "你是财务会计，负责根据记账守则执行记账操作。"

    def process(self, task: str) -> str:
        rules = self.read_rules()
        messages = self.build_messages(
            f"根据以下规则处理记账任务：\n{task}\n\n规则：\n{rules}",
            extra_context="给出结构化记账结果：\n类型：收入/支出/转账\n金额：（数字）\n说明：（描述）\n如有异常标注【异常】及原因。",
        )
        result = self.call_llm(messages)

        try:
            amount = self._extract_amount(result)
            type_ = self._extract_type(result)
            desc = self._extract_description(result)
            anomaly = self._detect_anomaly(result)

            if amount and type_ and desc:
                entry_id = write_entry(
                    datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    type_=type_,
                    amount=amount,
                    description=desc,
                    recorded_by=self.NAME,
                    anomaly_flag=anomaly["flag"],
                    anomaly_reason=anomaly["reason"],
                )
                result += f"\n\n[已记账 ID:{entry_id}]"
        except Exception:
            pass

        return result

    def _extract_amount(self, text: str) -> Optional[float]:
        import re

        match = re.search(r"金额[：:]\s*(\d+(?:\.\d+)?)", text)
        if match:
            return float(match.group(1))
        match = re.search(r"(\d+(?:\.\d+)?)\s*元", text)
        if match:
            return float(match.group(1))
        return None

    def _extract_type(self, text: str) -> Optional[str]:
        if "收入" in text:
            return "收入"
        if "转账" in text:
            return "转账"
        if "支出" in text:
            return "支出"
        return None

    def _extract_description(self, text: str) -> Optional[str]:
        import re

        match = re.search(r"说明[：:]\s*(.+)", text)
        if match:
            return match.group(1).strip()
        return None

    def _detect_anomaly(self, text: str) -> dict:
        anomaly: dict = {"flag": None, "reason": None}

        if "【异常】" in text or "⚠️" in text or "异常" in text:
            anomaly["flag"] = "medium"
            import re

            match = re.search(r"异常[：:]\s*(.+)", text)
            if match:
                anomaly["reason"] = match.group(1).strip()

        amount = self._extract_amount(text)
        if amount:
            if amount < 10:
                anomaly["flag"] = "high"
                anomaly["reason"] = f"金额过小: {amount}元"
            elif amount > 100000:
                anomaly["flag"] = "high"
                anomaly["reason"] = f"金额过大: {amount}元"

        return anomaly
