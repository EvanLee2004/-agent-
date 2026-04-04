"""DeerFlow 财务部门工具上下文。"""

from dataclasses import dataclass

from accounting.query_vouchers_router import QueryVouchersRouter
from accounting.record_voucher_router import RecordVoucherRouter
from audit.audit_voucher_router import AuditVoucherRouter
from cashier.query_cash_transactions_router import QueryCashTransactionsRouter
from cashier.record_cash_transaction_router import RecordCashTransactionRouter
from department.collaboration.generate_fiscal_task_prompt_router import GenerateFiscalTaskPromptRouter
from rules.reply_with_rules_router import ReplyWithRulesRouter
from tax.calculate_tax_router import CalculateTaxRouter


@dataclass(frozen=True)
class FinanceDepartmentToolContext:
    """描述 DeerFlow 可见的财务部门工具上下文。

    DeerFlow 的工具变量通过 `module:variable` 静态路径解析，因此工具对象无法像普通
    应用层那样在运行时逐个注入依赖。这里将路由对象聚合成受控上下文，是为了把这一
    第三方运行时约束限制在 `runtime/deerflow/`，避免财务业务模块反过来感知底层
    agent 引擎的装配方式。

    阶段 3 说明：多 agent 协作已切换为 DeerFlow 原生 task/subagent 机制，
    collaborate_with_department_role 工具已移除。财务专业化 prompt 生成由
    generate_fiscal_task_prompt 工具提供（阶段 2 落地）。

    记忆功能由 DeerFlow 原生机制接管（memory.enabled=True）。
    """

    record_voucher_router: RecordVoucherRouter
    query_vouchers_router: QueryVouchersRouter
    calculate_tax_router: CalculateTaxRouter
    audit_voucher_router: AuditVoucherRouter
    record_cash_transaction_router: RecordCashTransactionRouter
    query_cash_transactions_router: QueryCashTransactionsRouter
    reply_with_rules_router: ReplyWithRulesRouter
    generate_fiscal_task_prompt_router: GenerateFiscalTaskPromptRouter
