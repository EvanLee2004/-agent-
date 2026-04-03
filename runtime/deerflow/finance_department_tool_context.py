"""DeerFlow 财务部门工具上下文。"""

from dataclasses import dataclass

from accounting.query_vouchers_router import QueryVouchersRouter
from accounting.record_voucher_router import RecordVoucherRouter
from audit.audit_voucher_router import AuditVoucherRouter
from cashier.query_cash_transactions_router import QueryCashTransactionsRouter
from cashier.record_cash_transaction_router import RecordCashTransactionRouter
from department.collaboration.collaborate_with_department_role_router import CollaborateWithDepartmentRoleRouter
from memory.search_memory_router import SearchMemoryRouter
from memory.store_memory_router import StoreMemoryRouter
from rules.reply_with_rules_router import ReplyWithRulesRouter
from tax.calculate_tax_router import CalculateTaxRouter


@dataclass(frozen=True)
class FinanceDepartmentToolContext:
    """描述 DeerFlow 可见的财务部门工具上下文。

    DeerFlow 的工具变量通过 `module:variable` 静态路径解析，因此工具对象无法像普通
    应用层那样在运行时逐个注入依赖。这里将路由对象聚合成受控上下文，是为了把这一
    第三方运行时约束限制在 `runtime/deerflow/`，避免财务业务模块反过来感知底层
    agent 引擎的装配方式。
    """

    record_voucher_router: RecordVoucherRouter
    query_vouchers_router: QueryVouchersRouter
    calculate_tax_router: CalculateTaxRouter
    audit_voucher_router: AuditVoucherRouter
    record_cash_transaction_router: RecordCashTransactionRouter
    query_cash_transactions_router: QueryCashTransactionsRouter
    store_memory_router: StoreMemoryRouter
    search_memory_router: SearchMemoryRouter
    reply_with_rules_router: ReplyWithRulesRouter
    collaborate_with_department_role_router: CollaborateWithDepartmentRoleRouter
