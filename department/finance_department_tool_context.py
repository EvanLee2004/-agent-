"""财务部门工具上下文。"""

from dataclasses import dataclass

from accounting.query_vouchers_router import QueryVouchersRouter
from accounting.record_voucher_router import RecordVoucherRouter
from audit.audit_voucher_router import AuditVoucherRouter
from cashier.query_cash_transactions_router import QueryCashTransactionsRouter
from cashier.record_cash_transaction_router import RecordCashTransactionRouter
from department.collaborate_with_department_role_router import CollaborateWithDepartmentRoleRouter
from memory.search_memory_router import SearchMemoryRouter
from memory.store_memory_router import StoreMemoryRouter
from rules.reply_with_rules_router import ReplyWithRulesRouter
from tax.calculate_tax_router import CalculateTaxRouter


@dataclass(frozen=True)
class FinanceDepartmentToolContext:
    """描述财务部门工具上下文。

    DeerFlow 的工具变量通过 `module:variable` 静态路径解析，因此工具对象无法像普通
    应用层那样在运行时逐个注入依赖。这里将路由对象聚合成受控上下文，是为了把这一
    第三方框架约束限制在部门边界，而不是让全项目都退化成服务定位器。

    Attributes:
        record_voucher_router: 记账工具入口。
        query_vouchers_router: 查账工具入口。
        calculate_tax_router: 税务工具入口。
        audit_voucher_router: 审核工具入口。
        record_cash_transaction_router: 资金收付记录工具入口。
        query_cash_transactions_router: 资金收付查询工具入口。
        store_memory_router: 写记忆工具入口。
        search_memory_router: 查记忆工具入口。
        reply_with_rules_router: 规则问答工具入口。
        collaborate_with_department_role_router: 角色协作工具入口。
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
