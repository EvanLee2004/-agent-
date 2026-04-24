"""会计领域服务工厂。"""

from accounting.accounting_service import AccountingService
from accounting.chart_of_accounts_repository import ChartOfAccountsRepository
from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.journal_repository import JournalRepository
from accounting.sqlite_chart_of_accounts_repository import SQLiteChartOfAccountsRepository
from accounting.sqlite_journal_repository import SQLiteJournalRepository
from app.accounting_domain_service_bundle import AccountingDomainServiceBundle


class AccountingDomainServiceFactory:
    """装配会计核算所需的领域服务。"""

    def build(
        self,
        department_display_name: str,
        chart_repository: ChartOfAccountsRepository | None = None,
        journal_repository: JournalRepository | None = None,
    ) -> AccountingDomainServiceBundle:
        """构造会计领域服务集合。"""
        chart_repository = chart_repository or SQLiteChartOfAccountsRepository()
        journal_repository = journal_repository or SQLiteJournalRepository()
        chart_service = ChartOfAccountsService(chart_repository)
        accounting_service = AccountingService(
            journal_repository,
            chart_service,
            department_display_name,
        )
        return AccountingDomainServiceBundle(
            department_display_name=department_display_name,
            accounting_service=accounting_service,
            chart_of_accounts_service=chart_service,
            journal_repository=journal_repository,
        )
