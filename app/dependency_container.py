"""依赖注入容器。"""

from app.application_bootstrapper import ApplicationBootstrapper
from app.application_bootstrapper_factory import ApplicationBootstrapperFactory
from app.conversation_router_factory import ConversationRouterFactory
from configuration.configuration_service import ConfigurationService
from configuration.file_configuration_repository import FileConfigurationRepository
from configuration.llm_configuration import LlmConfiguration
from configuration.provider_catalog import ProviderCatalog
from conversation.conversation_router import ConversationRouter
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog


class DependencyContainer:
    """依赖注入容器。"""

    def __init__(self, llm_configuration: LlmConfiguration):
        self._llm_configuration = llm_configuration
        self._role_catalog = FinanceDepartmentRoleCatalog()

    def build_conversation_router(self) -> ConversationRouter:
        """构造会话入口。"""
        return ConversationRouterFactory(
            self._llm_configuration,
            self._role_catalog,
        ).build()

    def build_application_bootstrapper(self) -> ApplicationBootstrapper:
        """构造引导器。"""
        return ApplicationBootstrapperFactory().build()

    @staticmethod
    def create_configuration_service() -> ConfigurationService:
        """构造独立配置服务。

        Returns:
            CLI 启动阶段可直接使用的配置服务。
        """
        return ConfigurationService(FileConfigurationRepository(), ProviderCatalog())
