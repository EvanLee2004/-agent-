"""会计 Agent，负责记账

Accountant 是执行记账的 Agent：
1. 用 think() 分析记账需求
2. 用 execute() 执行记账（写入数据库）
3. 用 reflect() 反思审核反馈，尝试自我修正
"""

from datetime import datetime
from typing import Optional

from agents.base import BaseAgent
from core.ledger import write_entry
from core.schemas import ThoughtResult, AuditResult


class Accountant(BaseAgent):
    """会计 Agent

    职责：
    - 根据记账请求执行记账操作
    - 检测异常情况
    - 根据审核反馈修正错误

    继承自 BaseAgent，获得了：
    - think() 方法：分析记账需求
    - execute() 方法：执行记账动作
    - reflect() 方法：反思反馈，尝试修正
    - call_llm() 方法：调用 LLM
    - read_rules() 方法：读取记账规则
    """

    NAME = "accountant"
    SYSTEM_PROMPT = "你是财务会计，负责根据记账守则执行记账操作。"

    def process(self, task: str) -> str:
        """处理记账任务（兼容旧接口）

        如果直接调用 process()，会走完整的 think → execute 流程

        Args:
            task: 记账任务描述

        Returns:
            记账结果字符串
        """
        thought = self.think(task)
        return self.execute(thought, {})

    def execute(self, plan: ThoughtResult, context: dict) -> str:
        """执行记账

        根据 plan.entities 里的信息执行记账操作：
        - 从 entities 提取金额、类型、说明
        - 写入数据库
        - 检测异常

        Args:
            plan: think() 返回的结构化思考结果，包含：
                  - intent: accounting
                  - entities: {"amount": 500, "type": "支出", "description": "午餐"}
            context: 额外上下文（当前未使用）

        Returns:
            记账结果描述字符串
        """
        rules = self.read_rules()
        entities = plan.entities

        # 从 entities 提取记账信息
        amount = entities.get("amount")
        type_ = entities.get("type", "支出")  # 默认支出
        description = entities.get("description", "")

        # 如果 entities 里没有，尝试让 LLM 从原始任务理解
        if not amount or not description:
            messages = self.build_messages(
                f"从以下任务中提取记账信息（金额、类型、说明）：\n{plan.reasoning or entities}",
                extra_context=(
                    "从任务中提取信息，返回 JSON 格式：\n"
                    '{"amount": 数字, "type": "收入"|"支出"|"转账", "description": "描述"}'
                ),
            )
            raw = self.call_llm(messages)
            # 解析 LLM 返回的 JSON
            import json

            try:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start != -1 and end != 0:
                    data = json.loads(raw[start:end])
                    amount = amount or data.get("amount")
                    type_ = type_ or data.get("type", "支出")
                    description = description or data.get("description", "")
            except Exception:
                pass

        # 构建记账描述
        record_desc = f"{type_} {amount}元"
        if description:
            record_desc += f" - {description}"

        # 检测异常
        anomaly = self._detect_anomaly(amount, type_, description)

        # 写入数据库
        if amount and type_:
            entry_id = write_entry(
                datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                type_=type_,
                amount=float(amount),
                description=description or record_desc,
                recorded_by=self.NAME,
                anomaly_flag=anomaly["flag"],
                anomaly_reason=anomaly["reason"],
            )
            result = f"[ID:{entry_id}] {record_desc}"
            if anomaly["flag"]:
                result += f" ⚠️ 异常: {anomaly['reason']}"
            return result

        return f"无法理解记账信息，请检查输入"

    def reflect(self, result: str, feedback: str) -> str:
        """反思审核反馈，尝试自我修正

        当审核发现问题时调用此方法：
        1. 将反馈记录到记忆
        2. 尝试理解错误原因

        Args:
            result: 之前的记账结果
            feedback: 审核反馈意见

        Returns:
            修正后的结果（如果能修正），否则返回原结果
        """
        if not feedback:
            return result

        # 将反馈记录到记忆，供后续参考
        self.update_memory(f"审核反馈: {feedback[:200]}")

        # TODO: 未来可以让 LLM 分析反馈，尝试自动修正
        # 目前只是记录，不做自动修正

        return result

    def _detect_anomaly(
        self, amount: Optional[float], type_: str, description: str
    ) -> dict:
        """检测记账异常

        根据金额大小、类型等判断是否有异常

        Args:
            amount: 金额
            type_: 类型（收入/支出/转账）
            description: 描述

        Returns:
            dict: {"flag": "high"|"medium"|None, "reason": str}
        """
        anomaly: dict = {"flag": None, "reason": None}

        if amount is None:
            return anomaly

        # 金额异常检测
        if amount < 10:
            anomaly["flag"] = "high"
            anomaly["reason"] = f"金额过小: {amount}元"
        elif amount > 100000:
            anomaly["flag"] = "high"
            anomaly["reason"] = f"金额过大: {amount}元"
        elif amount > 50000:
            anomaly["flag"] = "medium"
            anomaly["reason"] = f"金额较大: {amount}元，需确认"

        # 如果描述中提到异常关键词
        if "异常" in description or "问题" in description:
            if anomaly["flag"]:
                anomaly["reason"] += f"，另: {description}"
            else:
                anomaly["flag"] = "medium"
                anomaly["reason"] = description

        return anomaly
