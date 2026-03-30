"""经理 Agent，协调流程、汇总返回"""

from agents.base import BaseAgent
from agents.accountant import Accountant  # 会计，负责记账
from agents.auditor import Auditor  # 审核，负责审查
from core.ledger import get_entries, init_ledger_db  # 账目数据库操作


class Manager(BaseAgent):
    NAME = "manager"
    SYSTEM_PROMPT = (
        "你是财务部门的经理，负责理解用户意图、协调会计和审核的工作、汇总结果返回用户。"
    )

    def process(self, task: str) -> str:
        """处理用户任务的入口方法

        根据用户输入判断是「记账请求」还是「查询请求」
        - 包含「查/看/今天/记账」关键词 → 查账
        - 其他 → 记账
        """
        # 确保账目数据库已初始化（表存在）
        init_ledger_db()

        # 关键词匹配，判断任务类型
        if any(kw in task for kw in ["查", "看", "今天", "记账"]):
            return self._handle_review(task)  # 查询记账记录

        return self._handle_accounting(task)  # 执行记账

    def _handle_accounting(self, task: str) -> str:
        """处理记账请求：会计记账 → 审核审查 → 返回结果

        最多3轮讨论，直到审核通过或超时
        """
        accountant = Accountant()  # 创建会计实例
        auditor = Auditor()  # 创建审核实例
        current = task  # 当前待处理的任务
        result = ""  # 会计的记账结果
        audit = ""  # 审核的审查结果

        # 最多讨论3轮
        for i in range(3):
            # 第1步：会计根据规则记账
            result = accountant.handle(current)

            # 第2步：审核审查记账结果
            audit = auditor.handle(result)

            # 第3步：检查是否通过
            if "审核通过" in audit:
                return f"✅ 通过\n\n{result}"

            # 第4步：未通过，把审核意见反馈给会计，让其修改
            current = f"请修改：{audit}"

        # 3轮还没通过，返回人工介入提示
        return f"⚠️ 3轮未通过，需人工确认\n\n{audit}"

    def _handle_review(self, task: str) -> str:
        """处理查询请求：从数据库读取记录，表格展示给用户

        表格列：ID、时间、类型、金额、说明、状态
        异常记录前面标 ⚠️
        """
        # 从数据库获取最近50条记录
        entries = get_entries(limit=50)

        if not entries:
            return "暂无记录"

        # 构建表格头部
        lines = [
            f"{'ID':^3} {'时间':^18} {'类型':^4} {'金额':^10} {'说明':^15} {'状态':^6}"
        ]

        # 遍历每条记录，格式化输出
        for e in entries:
            # 有异常标记的记录标 ⚠️
            flag = "⚠️" if e.get("anomaly_flag") else ""

            # 状态文字映射
            status = {"pending": "待审", "approved": "✅", "rejected": "❌"}.get(
                e.get("status", ""), ""
            )

            # 格式化每行：ID + 时间 + 类型 + 金额 + 说明(截断) + 状态
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


# 全局单例，供 main.py 直接导入使用
manager = Manager()
