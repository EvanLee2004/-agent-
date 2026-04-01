"""应用启动引导模块。

该模块是当前项目的 composition root 之一，负责把所有“启动时只做一次”的
副作用操作集中收口，避免这些逻辑散落到 Agent 构造函数、CLI 入口或测试中。

当前引导职责包括：
1. 初始化新版账务表结构（科目、凭证、分录）
2. 灌入默认会计科目
"""

from typing import Optional

from infrastructure.accounting_repository import (
    IChartOfAccountsRepository,
    IJournalRepository,
    get_chart_of_accounts_repository,
    get_journal_repository,
)
from services.chart_of_accounts_service import ChartOfAccountsService


class ApplicationBootstrapper:
    """应用启动引导器。"""

    def __init__(
        self,
        chart_repository: Optional[IChartOfAccountsRepository] = None,
        journal_repository: Optional[IJournalRepository] = None,
        chart_of_accounts_service: Optional[ChartOfAccountsService] = None,
    ):
        self._chart_repository = chart_repository or get_chart_of_accounts_repository()
        self._journal_repository = journal_repository or get_journal_repository()
        self._chart_of_accounts_service = chart_of_accounts_service or ChartOfAccountsService(
            self._chart_repository
        )

    def initialize(self) -> None:
        """执行应用初始化。

        这里只初始化当前主架构真正需要的数据库对象：
        - 会计科目表
        - 凭证头
        - 分录行

        旧 ledger 体系已经完全移除，避免启动阶段继续创建无意义的历史表。
        """
        self._chart_repository.init_db()
        self._journal_repository.init_db()
        self._chart_of_accounts_service.initialize_default_subjects()


def bootstrap_default_application() -> None:
    """初始化默认运行时环境。"""
    ApplicationBootstrapper().initialize()
