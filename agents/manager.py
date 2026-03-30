"""经理 Agent，协调流程、汇总返回"""

from agents.base import BaseAgent
from agents.accountant import Accountant
from agents.auditor import Auditor
from core.ledger import get_entries, init_ledger_db


class Manager(BaseAgent):
    NAME = "manager"
    SYSTEM_PROMPT = (
        "你是财务部门的经理，负责理解用户意图、协调会计和审核的工作、汇总结果返回用户。"
    )

    def process(self, task: str) -> str:
        init_ledger_db()

        if any(kw in task for kw in ["查", "看", "今天", "记账"]):
            return self._handle_review(task)

        return self._handle_accounting(task)

    def _handle_accounting(self, task: str) -> str:
        accountant = Accountant()
        auditor = Auditor()
        current = task
        result = ""
        audit = ""

        for i in range(3):
            result = accountant.handle(current)
            audit = auditor.handle(result)

            if "审核通过" in audit:
                return f"✅ 通过\n\n{result}"

            current = f"请修改：{audit}"

        return f"⚠️ 3轮未通过，需人工确认\n\n{audit}"

    def _handle_review(self, task: str) -> str:
        entries = get_entries(limit=50)
        if not entries:
            return "暂无记录"

        lines = [
            f"{'ID':^3} {'时间':^18} {'类型':^4} {'金额':^10} {'说明':^15} {'状态':^6}"
        ]
        for e in entries:
            flag = "⚠️" if e.get("anomaly_flag") else ""
            status = {"pending": "待审", "approved": "✅", "rejected": "❌"}.get(
                e.get("status", ""), ""
            )
            lines.append(
                f"{flag}{e['id']:>2} {e['datetime'][:16]:^18} {e['type']:^4} ¥{e['amount']:>8.2f} {e['description'][:12]:<12} {status:^6}"
            )

        total_in = sum(e["amount"] for e in entries if e["type"] == "收入")
        total_out = sum(e["amount"] for e in entries if e["type"] == "支出")
        lines.append(
            f"\n收入: ¥{total_in:.2f}  支出: ¥{total_out:.2f}  结余: ¥{total_in - total_out:.2f}"
        )
        return "\n".join(lines)


manager = Manager()
