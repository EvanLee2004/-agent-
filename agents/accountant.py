"""Accountant Agent - 执行记账操作

Accountant 是执行记账的 Agent，负责：
1. 调用 Skill 获取 prompt
2. 用 LLM 统一处理
3. 写账本数据库
4. 记录反馈到记忆
"""

import re
from datetime import datetime
from typing import Any, Optional

from agents.base import BaseAgent
from core.ledger import write_entry
from core.llm import LLMClient
from core.skill_loader import SkillLoader


class Accountant(BaseAgent):
    """会计 Agent（执行者）。

    负责根据记账请求执行记账操作，包括：
    - 调用 Skill 脚本获取 prompt
    - 统一调 LLM 获取结果
    - 写入账本数据库
    - 根据审核反馈修正错误

    Attributes:
        NAME: Agent 名称标识
        SYSTEM_PROMPT: 系统提示词，从 Skill 加载
        _feedback: 上次审核反馈，用于循环修正

    Example:
        >>> accountant = Accountant()
        >>> result = accountant.process("报销1000元差旅费")
        >>> print(result)
        "[ID:1] 支出 1000.0元 - 差旅费报销"
    """

    NAME: str = "accounting"

    def __init__(self) -> None:
        """初始化 Accountant。

        从 Skill 加载 SYSTEM_PROMPT，如果加载失败则使用默认提示词。
        初始化反馈为空字符串。
        """
        try:
            skill = SkillLoader.load(self.NAME)
            self.SYSTEM_PROMPT = skill["system_prompt"]
        except FileNotFoundError:
            self.SYSTEM_PROMPT = "你是记账专家，负责执行记账操作。"
        self._feedback: str = ""

    def process(self, task: str) -> str:
        """处理记账任务。

        调用 Skill 获取 prompt，然后用 LLM 统一处理。

        工作流程：
        1. 调用 SkillLoader.execute_script 获取 prompt
        2. 构建 messages 调用 LLMClient.chat()
        3. 解析 LLM 响应
        4. 写入账本数据库
        5. 返回格式化结果

        Args:
            task: 记账任务描述，如"报销1000元差旅费"

        Returns:
            记账结果字符串，格式：
                - 成功: "[ID:x] 类型 金额元 - 说明"
                - 失败: "执行失败: xxx"
                - 数据库错误: "数据库写入失败: xxx"
        """
        args = [task, "--json"]
        if self._feedback:
            args.extend(["--feedback", self._feedback])

        result = SkillLoader.execute_script(
            "accounting",
            "execute",
            args,
        )

        if result.get("status") != "ok":
            return f"执行失败: {result.get('message')}"

        data = result.get("data")
        if not data:
            return f"执行失败: {result.get('message')}"

        messages = [
            {"role": "system", "content": data.get("system", "")},
            {"role": "user", "content": data.get("prompt", "")},
        ]

        try:
            llm_response = LLMClient.get_instance().chat(messages)
        except Exception as e:
            return f"LLM 调用失败: {str(e)}"

        parsed = self._parse_accounting_response(llm_response)

        if parsed["status"] == "error":
            return f"执行失败: {parsed['message']}"

        amount = parsed["amount"]
        type_ = parsed["type"]
        description = parsed["description"]
        anomaly = parsed["anomaly"]

        try:
            entry_id = write_entry(
                datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                type_=type_,
                amount=float(amount),
                description=description,
                recorded_by="accounting",
                anomaly_flag=anomaly.get("flag"),
                anomaly_reason=anomaly.get("reason"),
            )
        except Exception as e:
            return f"数据库写入失败: {str(e)}"

        msg = f"[ID:{entry_id}] {type_} {amount}元"
        if description:
            msg += f" - {description}"
        if anomaly.get("flag"):
            msg += f" ⚠️ {anomaly['reason']}"

        return msg

    @staticmethod
    def _parse_accounting_response(response: str) -> dict[str, Any]:
        """从 LLM 响应文本中解析记账信息。

        使用正则表达式从 LLM 返回的文本中提取金额、类型、说明，
        并进行异常检测。

        Args:
            response: LLM 返回的原始文本

        Returns:
            dict[str, Any]: 包含以下键的字典：
                - status: "ok" 或 "error"
                - amount: float | None, 金额
                - type: str | None, 类型（收入/支出/转账）
                - description: str | None, 说明
                - anomaly: dict, 异常信息
                    - flag: str | None, 异常级别
                    - reason: str | None, 异常原因
                - message: str, 错误信息（仅当 status="error" 时）
                - raw_response: str, 原始响应（仅当 status="error" 时）
        """
        amount: Optional[float] = None
        type_: Optional[str] = None
        description: Optional[str] = None

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

        if not amount or not type_:
            return {
                "status": "error",
                "message": f"无法理解记账信息：{response}",
                "raw_response": response,
            }

        anomaly: dict[str, Optional[str]] = {"flag": None, "reason": None}
        if amount is not None:
            if amount < 10:
                anomaly["flag"] = "high"
                anomaly["reason"] = f"金额过小: {amount}元"
            elif amount > 100000:
                anomaly["flag"] = "high"
                anomaly["reason"] = f"金额过大: {amount}元"
            elif amount > 50000:
                anomaly["flag"] = "medium"
                anomaly["reason"] = f"金额较大: {amount}元，需确认"

        return {
            "status": "ok",
            "amount": amount,
            "type": type_,
            "description": description,
            "anomaly": anomaly,
        }

    def reflect(self, feedback: str) -> None:
        """反思审核反馈，记录到记忆并更新内部状态。

        当审核不通过时，Manager 会调用此方法记录反馈，
        下一次 process() 调用时会将反馈传递给 Skill。

        Args:
            feedback: 审核反馈意见
        """
        if feedback:
            self._feedback = feedback[:500]
            self.update_memory(f"审核反馈: {feedback[:200]}")
