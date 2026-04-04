"""应用服务工厂。

统一创建财务仓储实例，并分别注入到会话入口工厂和引导器工厂。
这样做有两点好处：
1. 所有仓储复用同一组实例，不会因工厂间各自 new 而产生多份连接；
2. 测试时可以替换为 mock 实例，提升可测试性。
"""

from accounting.chart_of_accounts_repository import ChartOfAccountsRepository
from accounting.journal_repository import JournalRepository
from cashier.cashier_repository import CashierRepository
from app.application_bootstrapper import ApplicationBootstrapper
from app.application_bootstrapper_factory import ApplicationBootstrapperFactory
from app.conversation_router_factory import ConversationRouterFactory
from configuration.configuration_service import ConfigurationService
from configuration.file_configuration_repository import FileConfigurationRepository
from configuration.llm_configuration import LlmConfiguration
from configuration.provider_catalog import ProviderCatalog
from conversation.conversation_router import ConversationRouter
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog


class AppServiceFactory:
    """应用服务工厂。

    统一管理财务仓储实例的创建，并负责把它们注入到下游工厂。
    与传统依赖注入容器的区别：此处没有容器框架，只是通过工厂方法显式
    传递依赖。这在保持测试灵活性的同时，避免了框架引入的复杂性。
    """

    def __init__(self, llm_configuration: LlmConfiguration):
        self._llm_configuration = llm_configuration
        self._role_catalog = FinanceDepartmentRoleCatalog()
        # 延迟创建仓储实例，确保只在真正需要时才初始化
        self._chart_repository: ChartOfAccountsRepository | None = None
        self._journal_repository: JournalRepository | None = None
        self._cashier_repository: CashierRepository | None = None

    def _get_repositories(
        self,
    ) -> tuple[
        ChartOfAccountsRepository,
        JournalRepository,
        CashierRepository,
    ]:
        """获取或创建仓储实例。"""
        if self._chart_repository is None:
            from accounting.sqlite_chart_of_accounts_repository import (
                SQLiteChartOfAccountsRepository,
            )
            from accounting.sqlite_journal_repository import SQLiteJournalRepository
            from cashier.sqlite_cashier_repository import SQLiteCashierRepository

            self._chart_repository = SQLiteChartOfAccountsRepository()
            self._journal_repository = SQLiteJournalRepository()
            self._cashier_repository = SQLiteCashierRepository()
        return (
            self._chart_repository,
            self._journal_repository,
            self._cashier_repository,
        )

    def build_conversation_router(self) -> ConversationRouter:
        """构造会话入口。"""
        chart_repo, journal_repo, cashier_repo = self._get_repositories()
        return ConversationRouterFactory(
            llm_configuration=self._llm_configuration,
            role_catalog=self._role_catalog,
            chart_repository=chart_repo,
            journal_repository=journal_repo,
            cashier_repository=cashier_repo,
        ).build()

    def build_application_bootstrapper(self) -> ApplicationBootstrapper:
        """构造引导器。"""
        chart_repo, journal_repo, cashier_repo = self._get_repositories()
        return ApplicationBootstrapperFactory().build(
            chart_repository=chart_repo,
            journal_repository=journal_repo,
            cashier_repository=cashier_repo,
        )

    @staticmethod
    def create_configuration_service() -> ConfigurationService:
        """构造独立配置服务。

        Returns:
            CLI 启动阶段可直接使用的配置服务。
        """
        return ConfigurationService(FileConfigurationRepository(), ProviderCatalog())
