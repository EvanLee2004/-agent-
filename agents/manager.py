"""经理 Agent，协调流程、汇总返回。

Manager 是整个系统的入口和协调者：
1. 接收用户输入
2. 用 LLM 分析用户意图（accounting / review / transfer）
3. 根据意图路由到不同的处理函数
4. 协调 Accountant 和 Auditor 的工作流程
"""

from agents.base import BaseAgent
from agents.accountant import Accountant
from agents.auditor import Auditor
from core.ledger import get_entries, init_ledger_db
from core.llm import LLMClient
from core.skill_loader import SkillLoader


class Manager(BaseAgent):
    """经理 Agent。

    职责：
    - 理解用户意图（用 LLM 分析）
    - 协调会计和审核的工作
    - 汇总结果返回用户

    Attributes:
        NAME: Agent 名称
        SYSTEM_PROMPT: 从 Skill 加载
    """

    NAME = "coordination"

    def __init__(self):
        """初始化时从 Skill 加载 SYSTEM_PROMPT"""
        try:
            skill = SkillLoader.load(self.NAME)
            self.SYSTEM_PROMPT = skill["system_prompt"]
        except FileNotFoundError:
            self.SYSTEM_PROMPT = (
                "你是财务部门的经理，负责理解用户意图，"
                "协调会计和审核的工作、汇总结果返回用户。"
            )

    def process(self, task: str) -> str:
        """处理用户任务的入口方法。

        工作流程：
        1. 确保账目数据库已初始化
        2. 用 LLM 分析用户意图
        3. 根据意图类型路由到不同的处理函数

        Args:
            task: 用户输入的任务描述

        Returns:
            处理结果字符串
        """
        init_ledger_db()

        intent = self._classify_intent(task)

        if intent == "accounting":
            return self._handle_accounting(task)
        elif intent == "review":
            return self._handle_review()
        elif intent == "transfer":
            return self._handle_transfer(task)
        else:
            return "🤔 无法理解您的意图"

    def _classify_intent(self, task: str) -> str:
        """用 LLM 分析用户意图。

        Args:
            task: 用户任务

        Returns:
            意图类型：accounting / review / transfer / unknown
        """
        result = SkillLoader.execute_script(
            "coordination",
            "intent",
            [task, "--json"],
        )

        if result.get("status") != "ok":
            return "unknown"

        data = result.get("data")
        if not data:
            return "unknown"

        messages = [
            {"role": "system", "content": data.get("system", "")},
            {"role": "user", "content": data.get("prompt", "")},
        ]

        try:
            response = LLMClient.get_instance().chat(messages)
        except Exception:
            return "unknown"

        return self._parse_intent_response(response)

    @staticmethod
    def _parse_intent_response(response: str) -> str:
        """从 LLM 响应中解析意图。

        Args:
            response: LLM 返回的文本

        Returns:
            意图类型
        """
        response_lower = response.lower().strip()
        response_num = response_lower.split(".")[0].strip()

        if response_num == "2":
            return "review"
        elif response_num == "3":
            return "transfer"
        elif (
            response_num == "1"
            or "accounting" in response_lower
            or "记账" in response
            or "报销" in response
        ):
            return "accounting"
        else:
            return "unknown"

    def _handle_accounting(self, task: str) -> str:
        """处理记账请求。

        协调 Accountant 和 Auditor：
        1. Accountant 执行记账
        2. Auditor 审核检查
        3. 如果有问题，Accountant 反思修正
        4. 循环直到审核通过或达到最大轮数

        Args:
            task: 原始用户任务

        Returns:
            处理结果字符串
        """
        accountant = Accountant()
        auditor = Auditor()
        max_rounds = 3

        last_result = ""
        last_audit = ""

        for _ in range(max_rounds):
            last_result = accountant.process(task)
            last_audit = auditor.process(last_result)

            if "通过" in last_audit:
                return f"✅ {last_result}"

            accountant.reflect(last_audit)

        return f"⚠️ 经过{max_rounds}轮讨论仍有问题，需人工确认\n\n审核意见：{last_audit}"

    def _handle_review(self) -> str:
        """处理查询请求。

        从数据库读取账目记录，以表格形式展示给用户。
        异常记录会标记 ⚠️。

        Returns:
            格式化的账目表格
        """
        entries = get_entries(limit=50)

        if not entries:
            return "暂无记录"

        lines = [
            f"{'ID':^3} {'时间':^18} {'类型':^4} {'金额':^10} {'说明':^15} {'状态':^6}"
        ]

        for e in entries:
            flag = "⚠️" if e.get("anomaly_flag") else ""
            status_map = {
                "pending": "待审",
                "approved": "✅",
                "rejected": "❌",
            }
            status = status_map.get(e.get("status", ""), "")

            lines.append(
                f"{flag}{e['id']:>2} {e['datetime'][:16]:^18} "
                f"{e['type']:^4} ¥{e['amount']:>8.2f} "
                f"{e['description'][:12]:<12} {status:^6}"
            )

        total_in = sum(e["amount"] for e in entries if e["type"] == "收入")
        total_out = sum(e["amount"] for e in entries if e["type"] == "支出")
        lines.append(
            f"\n收入: ¥{total_in:.2f}  支出: ¥{total_out:.2f}  "
            f"结余: ¥{total_in - total_out:.2f}"
        )

        return "\n".join(lines)

    def _handle_transfer(self, task: str) -> str:
        """处理转账请求。

        转账是一种特殊的记账（一方支出、一方收入）。
        目前作为记账请求处理。

        Args:
            task: 原始用户任务

        Returns:
            处理结果字符串
        """
        return self._handle_accounting(task)


manager = Manager()
