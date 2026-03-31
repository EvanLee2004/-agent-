"""Manager Agent - 协调流程、汇总返回

Manager 是整个系统的入口 Agent，负责：
1. 接收用户输入
2. 分析用户意图（accounting / review / transfer）
3. 根据意图路由到不同的处理函数
4. 协调 Accountant 和 Auditor 的工作流程

工作流程：
- 用户输入 → 意图分类 → 路由分发 → 协调处理 → 返回结果
"""

from agents.base import BaseAgent
from agents.accountant import Accountant
from agents.auditor import Auditor
from core.ledger import get_entries, init_ledger_db
from core.llm import LLMClient
from core.skill_loader import SkillLoader


class Manager(BaseAgent):
    """经理 Agent（协调者）。

    负责理解用户意图，协调会计和审核的工作，汇总结果返回用户。

    Attributes:
        NAME: Agent 名称标识
        SYSTEM_PROMPT: 系统提示词，从 Skill 加载

    Example:
        >>> manager = Manager()
        >>> result = manager.handle("报销1000元差旅费")
        >>> print(result)
        "✅ [ID:1] 支出 1000.0元 - 差旅费报销"
    """

    NAME: str = "coordination"

    def __init__(self) -> None:
        """初始化 Manager。

        从 Skill 加载 SYSTEM_PROMPT，如果加载失败则使用默认提示词。
        """
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

        调用 coordination Skill 获取 prompt，然后通过 LLMClient 统一调用 LLM。

        Args:
            task: 用户任务描述

        Returns:
            意图类型字符串，可能的值：
                - "accounting": 记账相关
                - "review": 查看账目记录
                - "transfer": 转账
                - "unknown": 无法判断
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
        """从 LLM 响应文本中解析意图。

        Args:
            response: LLM 返回的原始文本

        Returns:
            意图类型字符串
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

        协调 Accountant 和 Auditor 的工作流程：
        1. Accountant 执行记账，生成记账记录
        2. Auditor 审核检查
        3. 如果有问题，Accountant 反思修正
        4. 循环直到审核通过或达到最大轮数

        Args:
            task: 原始用户任务描述

        Returns:
            处理结果字符串，格式：
                - 成功: "✅ [ID:x] 类型 金额元 - 说明"
                - 失败: "⚠️ 经过3轮讨论仍有问题，需人工确认\n\n审核意见：xxx"
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
            格式化的账目表格字符串

        Example:
            ID   时间                 类型   金额       说明          状态
            1    2026-04-01 15:30   支出   ¥1000.00   差旅费        ✅
            收入: ¥0.00  支出: ¥1000.00  结余: ¥-1000.00
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
        当前实现直接复用记账流程。

        Args:
            task: 原始用户任务描述

        Returns:
            处理结果字符串
        """
        return self._handle_accounting(task)


# 全局单例实例
manager = Manager()
