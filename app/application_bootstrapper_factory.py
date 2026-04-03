"""应用引导器工厂。"""

from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.sqlite_chart_of_accounts_repository import SQLiteChartOfAccountsRepository
from accounting.sqlite_journal_repository import SQLiteJournalRepository
from app.application_bootstrapper import ApplicationBootstrapper
from cashier.sqlite_cashier_repository import SQLiteCashierRepository


class ApplicationBootstrapperFactory:
    """负责构造应用引导器。

    引导器只关心“本地存储是否就绪”和“默认会计科目是否初始化”。把它的装配拆成独立
    工厂，可以避免依赖容器同时承担会话装配、运行时接入和启动初始化三类职责。
    """

    def build(self) -> ApplicationBootstrapper:
        """构造引导器实例。

        Returns:
            已完成仓储与服务装配的应用引导器。
        """
        chart_repository = SQLiteChartOfAccountsRepository()
        journal_repository = SQLiteJournalRepository()
        cashier_repository = SQLiteCashierRepository()
        chart_service = ChartOfAccountsService(chart_repository)
        return ApplicationBootstrapper(
            chart_repository,
            journal_repository,
            chart_service,
            cashier_repository,
        )
