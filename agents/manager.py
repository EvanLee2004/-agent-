"""经理 Agent，协调流程、汇总返回。

Manager 是整个系统的入口和协调者：
1. 接收用户输入
2. 用 think() 分析用户意图（accounting / review / transfer）
3. 根据意图路由到不同的处理函数
4. 使用 ReActWorkflow 协调 Accountant 和 Auditor 的工作流程
"""

from typing import Optional

from agents.base import BaseAgent
from agents.accountant import Accountant
from agents.auditor import Auditor
from core.ledger import get_entries, init_ledger_db
from core.schemas import ThoughtResult
from core.workflow import ReActWorkflow


class Manager(BaseAgent):
    """经理 Agent。

    职责：
    - 理解用户意图（用 LLM 分析）
    - 协调会计和审核的工作
    - 汇总结果返回用户

    Attributes:
        NAME: Agent 名称
        SYSTEM_PROMPT: 系统提示词
    """

    NAME = "manager"
    SYSTEM_PROMPT = (
        "你是财务部门的经理，负责理解用户意图，协调会计和审核的工作、汇总结果返回用户。"
    )

    def process(self, task: str) -> str:
        """处理用户任务的入口方法。

        工作流程：
        1. 确保账目数据库已初始化
        2. 用 think() 让 LLM 分析用户意图
        3. 根据意图类型路由到不同的处理函数

        Args:
            task: 用户输入的任务描述

        Returns:
            处理结果字符串
        """
        init_ledger_db()

        thought = self.think(
            task,
            hint=(
                "分析用户的财务意图，返回 JSON：\n"
                '{intent: "accounting"|"review"|"transfer"|"unknown", '
                'entities: {}, reasoning: "", confidence: 0.0-1.0}'
            ),
        )

        if thought.intent == "accounting":
            return self._handle_accounting(task, thought)
        elif thought.intent == "review":
            return self._handle_review(thought)
        elif thought.intent == "transfer":
            return self._handle_transfer(task, thought)
        else:
            return f"🤔 无法理解您的意图：{thought.reasoning}"

    def execute(self, plan: ThoughtResult, context: dict) -> str:
        """Manager 不执行具体动作，由 process 路由。

        Args:
            plan: think() 结果
            context: 上下文

        Returns:
            不返回有用结果
        """
        return "请使用 process() 方法"

    def _handle_accounting(
        self,
        task: str,
        thought: ThoughtResult,
    ) -> str:
        """处理记账请求。

        使用 ReActWorkflow 协调 Accountant 和 Auditor：
        1. Accountant 执行记账
        2. Auditor 审核检查
        3. 如果有问题，Accountant 反思修正
        4. 循环直到审核通过或达到最大轮数

        Args:
            task: 原始用户任务
            thought: think() 分析出的结构化结果

        Returns:
            处理结果字符串
        """
        accountant = Accountant()
        auditor = Auditor()

        workflow = ReActWorkflow(
            agent=accountant,
            auditor=auditor,
            max_rounds=3,
        )

        hint = (
            "分析记账任务，提取：\n"
            '{"amount": 金额, "type": "收入"|"支出"|"转账", '
            '"description": "描述"}'
        )

        result = workflow.run(task, hint=hint)
        return f"✅ 审核通过\n\n{result}"

    def _handle_review(self, thought: ThoughtResult) -> str:
        """处理查询请求。

        从数据库读取账目记录，以表格形式展示给用户。
        异常记录会标记 ⚠️。

        Args:
            thought: think() 分析出的结果（可能包含查询条件）

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

    def _handle_transfer(
        self,
        task: str,
        thought: ThoughtResult,
    ) -> str:
        """处理转账请求。

        转账是一种特殊的记账（一方支出、一方收入）。
        目前作为记账请求处理，未来可以扩展为独立逻辑。

        Args:
            task: 原始用户任务
            thought: think() 分析出的结果

        Returns:
            处理结果字符串
        """
        return self._handle_accounting(task, thought)


manager = Manager()
