"""应用引导器工厂。"""

from accounting.chart_of_accounts_repository import ChartOfAccountsRepository
from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.journal_repository import JournalRepository
from app.application_bootstrapper import ApplicationBootstrapper


class ApplicationBootstrapperFactory:
    """负责构造应用引导器。

    引导器只关心"本地存储是否就绪"和"默认会计科目是否初始化"。把它的装配拆成独立
    工厂，可以避免依赖容器同时承担会话装配、运行时接入和启动初始化三类职责。
    """

    def build(
        self,
        chart_repository: ChartOfAccountsRepository | None = None,
        journal_repository: JournalRepository | None = None,
    ) -> ApplicationBootstrapper:
        """构造引导器实例。

        Args:
            chart_repository: 科目仓储，未提供时使用 SQLite 实现。
            journal_repository: 凭证仓储，未提供时使用 SQLite 实现。

        Returns:
            已完成仓储与服务装配的应用引导器。
        """
        # 延迟导入避免循环依赖（具体实现在 app/ 层）
        from accounting.sqlite_chart_of_accounts_repository import (
            SQLiteChartOfAccountsRepository,
        )
        from accounting.sqlite_journal_repository import SQLiteJournalRepository

        chart_repository = chart_repository or SQLiteChartOfAccountsRepository()
        journal_repository = journal_repository or SQLiteJournalRepository()
        chart_service = ChartOfAccountsService(chart_repository)
        return ApplicationBootstrapper(
            chart_repository,
            journal_repository,
            chart_service,
        )
