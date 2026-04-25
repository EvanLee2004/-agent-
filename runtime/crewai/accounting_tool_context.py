"""crewAI 会计工具上下文。"""

from dataclasses import dataclass

from accounting.query_chart_of_accounts_router import QueryChartOfAccountsRouter
from accounting.query_vouchers_router import QueryVouchersRouter
from accounting.record_voucher_router import RecordVoucherRouter
from accounting.report_routers import (
    QueryAccountBalanceRouter,
    QueryLedgerEntriesRouter,
    QueryTrialBalanceRouter,
)
from accounting.voucher_lifecycle_routers import (
    PostVoucherRouter,
    ReverseVoucherRouter,
    VoidVoucherRouter,
)
from audit.audit_voucher_router import AuditVoucherRouter
from cashier.query_bank_transactions_router import QueryBankTransactionsRouter
from cashier.reconcile_bank_transaction_router import ReconcileBankTransactionRouter
from cashier.record_bank_transaction_router import RecordBankTransactionRouter
from cashier.unreconcile_bank_transaction_router import UnreconcileBankTransactionRouter
from cashier.voucher_suggestion_router import VoucherSuggestionRouter


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
    post_voucher_router: PostVoucherRouter
    void_voucher_router: VoidVoucherRouter
    reverse_voucher_router: ReverseVoucherRouter
    query_account_balance_router: QueryAccountBalanceRouter
    query_ledger_entries_router: QueryLedgerEntriesRouter
    query_trial_balance_router: QueryTrialBalanceRouter
    record_bank_transaction_router: RecordBankTransactionRouter
    query_bank_transactions_router: QueryBankTransactionsRouter
    reconcile_bank_transaction_router: ReconcileBankTransactionRouter
    unreconcile_bank_transaction_router: UnreconcileBankTransactionRouter
    voucher_suggestion_router: VoucherSuggestionRouter
