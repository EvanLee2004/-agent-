"""crewAI 会计工具上下文。"""

from dataclasses import dataclass

from accounting.query_chart_of_accounts_router import QueryChartOfAccountsRouter
from accounting.query_vouchers_router import QueryVouchersRouter
from accounting.record_voucher_router import RecordVoucherRouter
from audit.audit_voucher_router import AuditVoucherRouter


@dataclass(frozen=True)
class AccountingToolContext:
    """保存 crewAI 工具调用所需的业务路由。

    crewAI 工具对象由运行时层创建，但真正的会计规则仍在 accounting/audit
    业务模块内执行。用上下文集中持有路由有两个目的：

    1. 让工具包装器只负责“把 crewAI 调用转成业务路由调用”，不直接 new service。
    2. 让 API/CLI 每次请求都能通过 ContextVar 打开同一套业务依赖，避免工具层依赖全局单例。
    """

    record_voucher_router: RecordVoucherRouter
    query_vouchers_router: QueryVouchersRouter
    audit_voucher_router: AuditVoucherRouter
    query_chart_of_accounts_router: QueryChartOfAccountsRouter
