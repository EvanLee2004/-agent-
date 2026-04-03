"""应用引导器。"""

from accounting.chart_of_accounts_repository import ChartOfAccountsRepository
from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.journal_repository import JournalRepository
from cashier.cashier_repository import CashierRepository


class ApplicationBootstrapper:
    """应用引导器。"""

    def __init__(
        self,
        chart_of_accounts_repository: ChartOfAccountsRepository,
        journal_repository: JournalRepository,
        chart_of_accounts_service: ChartOfAccountsService,
        cashier_repository: CashierRepository,
    ):
        self._chart_of_accounts_repository = chart_of_accounts_repository
        self._journal_repository = journal_repository
        self._chart_of_accounts_service = chart_of_accounts_service
        self._cashier_repository = cashier_repository

    def initialize(self) -> None:
        """初始化数据库和默认会计科目。"""
        self._chart_of_accounts_repository.initialize_storage()
        self._journal_repository.initialize_storage()
        self._cashier_repository.initialize_storage()
        self._chart_of_accounts_service.initialize_default_subjects()
