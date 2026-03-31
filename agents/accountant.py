"""会计 Agent，负责记账。

Accountant 是执行记账的 Agent：
1. 用 Skill 理解记账需求
2. 调用 Skill 脚本执行记账
3. 写账本数据库
4. 记录反馈到记忆
"""

import os

from agents.base import BaseAgent
from core.ledger import write_entry
from core.skill_loader import SkillLoader


class Accountant(BaseAgent):
    """会计 Agent。

    职责：
    - 根据记账请求执行记账操作
    - 调用 Skill 脚本获取记账数据
    - 写入账本数据库
    - 根据审核反馈修正错误

    Attributes:
        NAME: Agent 名称
        SYSTEM_PROMPT: 从 Skill 加载
        _feedback: 上次审核反馈
    """

    NAME = "accounting"

    def __init__(self):
        """初始化时从 Skill 加载 SYSTEM_PROMPT"""
        try:
            skill = SkillLoader.load(self.NAME)
            self.SYSTEM_PROMPT = skill["system_prompt"]
        except FileNotFoundError:
            self.SYSTEM_PROMPT = "你是财务会计，负责执行记账操作。"
        self._feedback: str = ""

    def process(self, task: str) -> str:
        """处理记账任务。

        调用 Skill 脚本执行记账，然后写入数据库。
        如果有反馈，应包含修正后的信息。

        Args:
            task: 记账任务描述，如"报销1000元差旅费"

        Returns:
            记账结果字符串
        """
        args = [task, "--json"]
        if self._feedback:
            args.extend(["--feedback", self._feedback])

        result = SkillLoader.execute_script(
            "accounting",
            "execute",
            args,
            env={"LLM_API_KEY": os.environ.get("LLM_API_KEY", "")},
        )

        if result.get("status") != "ok":
            return f"执行失败: {result.get('message')}"

        data = result.get("data")
        if not data:
            return f"执行失败: {result.get('message')}"

        try:
            entry_id = write_entry(
                datetime=data["datetime"],
                type_=data["type"],
                amount=float(data["amount"]),
                description=data["description"],
                recorded_by=data.get("recorded_by", "accountant"),
                anomaly_flag=data.get("anomaly", {}).get("flag"),
                anomaly_reason=data.get("anomaly", {}).get("reason"),
            )
        except Exception as e:
            return f"数据库写入失败: {str(e)}"

        msg = f"[ID:{entry_id}] {data['type']} {data['amount']}元"
        if data.get("description"):
            msg += f" - {data['description']}"
        if data.get("anomaly", {}).get("flag"):
            msg += f" ⚠️ {data['anomaly']['reason']}"

        return msg

    def reflect(self, feedback: str) -> None:
        """反思审核反馈，记录到记忆并更新内部状态。

        Args:
            feedback: 审核反馈意见
        """
        if feedback:
            self._feedback = feedback[:500]
            self.update_memory(f"审核反馈: {feedback[:200]}")
