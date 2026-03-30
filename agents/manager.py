"""经理 Agent，协调流程、汇总返回

Manager 是整个系统的入口和协调者：
1. 接收用户输入
2. 用 think() 分析用户意图（accounting / review / transfer）
3. 根据意图路由到不同的处理函数
4. 协调 Accountant 和 Auditor 的工作流程
"""

from agents.base import BaseAgent
from agents.accountant import Accountant  # 会计，负责记账
from agents.auditor import Auditor  # 审核，负责审查
from core.ledger import get_entries, init_ledger_db  # 账目数据库操作
from core.schemas import ThoughtResult, AuditResult  # 结构化思考结果


class Manager(BaseAgent):
    """经理 Agent

    职责：
    - 理解用户意图（用 LLM 分析）
    - 协调会计和审核的工作
    - 汇总结果返回用户

    继承自 BaseAgent，获得了：
    - think() 方法：先用 LLM 思考任务
    - call_llm() 方法：调用 LLM
    - read_memory() / write_memory()：读写记忆
    """

    NAME = "manager"
    SYSTEM_PROMPT = (
        "你是财务部门的经理，负责理解用户意图、协调会计和审核的工作、汇总结果返回用户。"
    )

    def process(self, task: str) -> str:
        """处理用户任务的入口方法

        工作流程：
        1. 确保账目数据库已初始化
        2. 用 think() 让 LLM 分析用户意图
        3. 根据意图类型路由到不同的处理函数

        Args:
            task: 用户输入的任务描述

        Returns:
            处理结果字符串
        """
        # 确保账目数据库已初始化（表存在）
        init_ledger_db()

        # 第一步：用 LLM 思考分析用户意图
        thought = self.think(
            task,
            hint=(
                "分析用户的财务意图，返回 JSON：\n"
                '{intent: "accounting"|"review"|"transfer"|"unknown", '
                'entities: {}, reasoning: "", confidence: 0.0-1.0}'
            ),
        )

        # 第二步：根据意图类型路由到不同的处理函数
        if thought.intent == "accounting":
            # 记账请求：会计记账 → 审核审查
            return self._handle_accounting(task, thought)
        elif thought.intent == "review":
            # 查询请求：查看账目记录
            return self._handle_review(thought)
        elif thought.intent == "transfer":
            # 转账请求：作为特殊记账处理
            return self._handle_transfer(task, thought)
        else:
            # 无法理解的意图
            return f"🤔 无法理解您的意图：{thought.reasoning}"

    def _handle_accounting(self, task: str, thought: ThoughtResult) -> str:
        """处理记账请求

        工作流程（最多3轮）：
        1. Accountant 执行记账
        2. Auditor 审核检查
        3. 如果有问题，反馈给 Accountant 修正
        4. 循环直到审核通过或达到最大轮数

        Args:
            task: 原始用户任务
            thought: think() 分析出的结构化结果

        Returns:
            处理结果
        """
        accountant = Accountant()  # 创建会计实例
        auditor = Auditor()  # 创建审核实例
        current_task = task  # 当前待处理的任务（会随着反馈更新）
        audit_result: AuditResult = AuditResult(
            passed=False, comments=""
        )  # 初始化，避免 LSP 报错

        # 最多讨论3轮（Accountant + Auditor 的往返）
        for round_num in range(3):
            # 第1步：会计执行记账
            # 传入 thought，让会计知道从 entities 里提取信息
            result = accountant.execute(thought, {})

            # 第2步：审核审查记账结果
            audit_result = auditor.execute(thought, {"record": result})

            # 第3步：检查审核是否通过
            if audit_result.passed:
                # 审核通过，返回结果
                return f"✅ 审核通过\n\n{result}"

            # 第4步：审核未通过，把审核意见反馈给会计
            # Accountant 用 reflect() 反思自己的记账结果
            accountant.reflect(result, audit_result.comments)

            # 构建修正后的任务，让下一轮会计重新处理
            current_task = (
                f"请修改以下记账结果：\n{result}\n\n审核意见：{audit_result.comments}"
            )

        # 3轮还没通过，返回人工介入提示
        return f"⚠️ 经过3轮讨论仍有问题，需人工确认\n\n审核意见：{audit_result.comments}"

    def _handle_review(self, thought: ThoughtResult) -> str:
        """处理查询请求

        从数据库读取账目记录，以表格形式展示给用户
        异常记录会标记 ⚠️

        Args:
            thought: think() 分析出的结果（可能包含查询条件）

        Returns:
            格式化的账目表格
        """
        # 从数据库获取最近50条记录
        # TODO: 未来可以根据 thought.entities 里的条件过滤
        entries = get_entries(limit=50)

        if not entries:
            return "暂无记录"

        # 构建表格
        lines = [
            f"{'ID':^3} {'时间':^18} {'类型':^4} {'金额':^10} {'说明':^15} {'状态':^6}"
        ]

        # 遍历每条记录，格式化输出
        for e in entries:
            # 有异常标记的记录标 ⚠️
            flag = "⚠️" if e.get("anomaly_flag") else ""

            # 状态文字映射：pending → 待审，approved → ✅，rejected → ❌
            status_map = {"pending": "待审", "approved": "✅", "rejected": "❌"}
            status = status_map.get(e.get("status", ""), "")

            # 格式化每行
            # ID右对齐，时间截取前16字符，类型4字符居中，金额右对齐带¥，说明截断12字符
            lines.append(
                f"{flag}{e['id']:>2} {e['datetime'][:16]:^18} {e['type']:^4} "
                f"¥{e['amount']:>8.2f} {e['description'][:12]:<12} {status:^6}"
            )

        # 计算收支合计和结余
        total_in = sum(e["amount"] for e in entries if e["type"] == "收入")
        total_out = sum(e["amount"] for e in entries if e["type"] == "支出")
        lines.append(
            f"\n收入: ¥{total_in:.2f}  支出: ¥{total_out:.2f}  结余: ¥{total_in - total_out:.2f}"
        )

        return "\n".join(lines)

    def _handle_transfer(self, task: str, thought: ThoughtResult) -> str:
        """处理转账请求

        转账是一种特殊的记账（一方支出、一方收入）
        目前作为记账请求处理，未来可以扩展为独立逻辑

        Args:
            task: 原始用户任务
            thought: think() 分析出的结果

        Returns:
            处理结果
        """
        # 转账暂时归类为记账请求
        # 未来可以扩展：根据 entities 里的 from/to/amount 分别记账
        return self._handle_accounting(task, thought)


# 全局单例，供 main.py 直接导入使用
# 这样可以避免每次都创建新实例
manager = Manager()
