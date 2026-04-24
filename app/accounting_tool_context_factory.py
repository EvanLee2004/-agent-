"""会计工具上下文工厂。"""

from accounting.accounting_service import AccountingService
from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.query_chart_of_accounts_router import QueryChartOfAccountsRouter
from accounting.query_vouchers_router import QueryVouchersRouter
from accounting.record_voucher_router import RecordVoucherRouter
from accounting.journal_repository import JournalRepository
from audit.audit_service import AuditService
from audit.audit_voucher_router import AuditVoucherRouter
from runtime.crewai.accounting_tool_context import AccountingToolContext


class AccountingToolContextFactory:
    """构造 crewAI 工具可见的会计业务上下文。"""

    def build(
        self,
        accounting_service: AccountingService,
        chart_of_accounts_service: ChartOfAccountsService,
        journal_repository: JournalRepository,
    ) -> AccountingToolContext:
        """构造会计工具上下文。"""
        return AccountingToolContext(
            record_voucher_router=RecordVoucherRouter(accounting_service),
            query_vouchers_router=QueryVouchersRouter(accounting_service),
            audit_voucher_router=AuditVoucherRouter(AuditService(journal_repository)),
            query_chart_of_accounts_router=QueryChartOfAccountsRouter(
                chart_of_accounts_service
            ),
        )
