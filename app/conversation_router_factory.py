"""会话入口工厂。

负责装配会话主链路，包含：
- crewAI 会计运行时作用域（runtime_root 可按请求注入）
- 会计工具上下文注册（使用 open_context_scope 实现请求级生命周期）
- 依赖装配

本工厂生成 AppConversationHandler（API）或 CliConversationHandler（CLI），
两者内部都持有纯净的 ConversationRouter 和 tool_context，
在 handle() 中统一管理请求级作用域和错误翻译。
"""

from pathlib import Path
from typing import Optional

from accounting.chart_of_accounts_repository import ChartOfAccountsRepository
from accounting.journal_repository import JournalRepository
from configuration.llm_configuration import LlmConfiguration
from conversation.conversation_router import ConversationRouter
from conversation.conversation_service import ConversationService
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from department.accounting_department_role_catalog import AccountingDepartmentRoleCatalog

from app.accounting_domain_service_factory import AccountingDomainServiceFactory
from app.accounting_tool_context_factory import AccountingToolContextFactory
from app.conversation_request_handler import AppConversationHandler
from app.cli_conversation_handler import CliConversationHandler
from app.department_orchestration_bundle import DepartmentOrchestrationBundle
from app.department_orchestration_factory import DepartmentOrchestrationFactory


class ConversationRouterFactory:
    """负责装配会话主链路。

    当前系统的主链路跨越会话边界、会计部门协作、crewAI 运行时和会计工具上下文。
    把这些装配细节从 `AppServiceFactory` 中抽出来，是为了让依赖容器回到"入口协调"
    的角色，而不是继续充当全系统构造脚本。

    设计说明：
    - runtime_root 可显式传入，实现文件路径隔离（API 场景推荐）
    - 会计工具上下文通过 open_context_scope() 在 AppConversationHandler.handle() 中实现请求级作用域
    - ConversationRouter 保持纯净，不包含作用域管理和错误翻译
    - 错误翻译由调用方（AppConversationHandler/CliConversationHandler）负责
    """

    def __init__(
        self,
        llm_configuration: LlmConfiguration,
        role_catalog: AccountingDepartmentRoleCatalog,
        chart_repository: ChartOfAccountsRepository,
        journal_repository: JournalRepository,
        runtime_root: Optional[Path] = None,
        orchestration_bundle: Optional[DepartmentOrchestrationBundle] = None,
    ):
        """构造工厂。

        Args:
            llm_configuration: LLM 配置。
            role_catalog: 会计部门角色目录。
            chart_repository: 科目仓储。
            journal_repository: 凭证仓储。
            runtime_root: crewAI 运行时根目录。
                传入独立路径可实现文件路径隔离（API 场景推荐）。
                为 None 时使用 DepartmentOrchestrationFactory 的默认值。
            orchestration_bundle: 预构建的部门编排 bundle。
                如提供，则直接使用而非内部创建（API 场景应传入以确保共享）。
        """
        self._llm_configuration = llm_configuration
        self._role_catalog = role_catalog
        self._chart_repository = chart_repository
        self._journal_repository = journal_repository
        self._runtime_root = runtime_root
        self._orchestration_bundle = orchestration_bundle

    def build_api_handler(self) -> AppConversationHandler:
        """构造 API 用的请求处理器。

        返回 AppConversationHandler，内部持有纯净的 ConversationRouter
        和 tool_context，在 handle() 中统一管理请求级作用域和异常翻译。

        Returns:
            已完成运行时和业务依赖装配的 API 请求处理器。
        """
        router, tool_context = self._build_router_and_context()
        return AppConversationHandler(router, tool_context)

    def build_cli_handler(self) -> CliConversationHandler:
        """构造 CLI 用的请求处理器。

        返回 CliConversationHandler，异常翻译为用户友好中文文本。

        Returns:
            CLI 请求处理器。
        """
        router, tool_context = self._build_router_and_context()
        return CliConversationHandler(router, tool_context)

    def _build_router_and_context(self):
        """构造纯净的 ConversationRouter 和 tool_context。

        如果在 __init__ 中传入了 orchestration_bundle，则直接使用；
        否则内部创建（保留向后兼容）。
        """
        if self._orchestration_bundle is None:
            orchestration_factory = DepartmentOrchestrationFactory(
                role_catalog=self._role_catalog,
                configuration=self._llm_configuration,
                runtime_root=self._runtime_root,
            )
            self._orchestration_bundle = orchestration_factory.build()

        department_display_name = self._role_catalog.get_department_display_name()
        domain_services = AccountingDomainServiceFactory().build(
            department_display_name,
            chart_repository=self._chart_repository,
            journal_repository=self._journal_repository,
        )
        accounting_tool_context = AccountingToolContextFactory().build(
            accounting_service=domain_services.accounting_service,
            chart_of_accounts_service=domain_services.chart_of_accounts_service,
            journal_repository=domain_services.journal_repository,
        )
        conversation_service = ConversationService(
            accounting_department_service=self._orchestration_bundle.accounting_department_service,
            reply_text_sanitizer=ReplyTextSanitizer(),
        )
        router = ConversationRouter(conversation_service)
        return router, accounting_tool_context
