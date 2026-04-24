"""会计领域服务装配结果。"""

from dataclasses import dataclass

from accounting.accounting_service import AccountingService
from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.journal_repository import JournalRepository


@dataclass(frozen=True)
class AccountingDomainServiceBundle:
    """会计部门主链路所需的领域服务集合。"""

    department_display_name: str
    accounting_service: AccountingService
    chart_of_accounts_service: ChartOfAccountsService
    journal_repository: JournalRepository
