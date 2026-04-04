"""会话入口工厂。"""

from accounting.chart_of_accounts_repository import ChartOfAccountsRepository
from accounting.journal_repository import JournalRepository
from cashier.cashier_repository import CashierRepository
from configuration.llm_configuration import LlmConfiguration
from conversation.conversation_router import ConversationRouter
from conversation.conversation_service import ConversationService
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog
from runtime.deerflow.finance_department_tool_context_registry import FinanceDepartmentToolContextRegistry

from app.department_orchestration_factory import DepartmentOrchestrationFactory
from app.finance_domain_service_bundle import FinanceDomainServiceBundle
from app.finance_domain_service_factory import FinanceDomainServiceFactory
from app.finance_tool_context_factory import FinanceToolContextFactory


class ConversationRouterFactory:
    """负责装配会话主链路。

    当前系统的主链路跨越会话边界、财务部门协作、DeerFlow 运行时和财务工具上下文。
    把这些装配细节从 `AppServiceFactory` 中抽出来，是为了让依赖容器回到"入口协调"
    的角色，而不是继续充当全系统构造脚本。

    阶段 3 说明：多 agent 协作已迁移至 DeerFlow 原生 task/subagent 机制，
    DepartmentCollaborationService 不再被使用。工具上下文中的 generate_fiscal_task_prompt_router
    为自包含组件，装配时无需传入协作服务。
    """

    def __init__(
        self,
        llm_configuration: LlmConfiguration,
        role_catalog: FinanceDepartmentRoleCatalog,
        chart_repository: ChartOfAccountsRepository,
        journal_repository: JournalRepository,
        cashier_repository: CashierRepository,
    ):
        self._llm_configuration = llm_configuration
        self._role_catalog = role_catalog
        self._chart_repository = chart_repository
        self._journal_repository = journal_repository
        self._cashier_repository = cashier_repository

    def build(self) -> ConversationRouter:
        """构造会话入口。

        Returns:
            已完成运行时和业务依赖装配的会话入口。
        """
        return ConversationRouter(self._build_conversation_service())

    def _build_conversation_service(self) -> ConversationService:
        """构造会话服务。"""
        department_display_name = self._role_catalog.get_department_display_name()
        domain_services = FinanceDomainServiceFactory().build(
            department_display_name,
            chart_repository=self._chart_repository,
            journal_repository=self._journal_repository,
            cashier_repository=self._cashier_repository,
        )
        orchestration_bundle = DepartmentOrchestrationFactory(
            role_catalog=self._role_catalog,
            configuration=self._llm_configuration,
        ).build()
        self._register_tool_context(domain_services)
        return ConversationService(
            orchestration_bundle.finance_department_service,
            ReplyTextSanitizer(),
        )

    def _register_tool_context(
        self,
        domain_services: FinanceDomainServiceBundle,
    ) -> None:
        """注册 DeerFlow 财务工具上下文。

        阶段 3：collaborate_with_department_role 已移除，工具上下文只包含
        财务业务工具和 generate_fiscal_task_prompt（自包含，无需协作服务）。
        """
        finance_tool_context = FinanceToolContextFactory().build(
            accounting_service=domain_services.accounting_service,
            journal_repository=domain_services.journal_repository,
            cashier_service=domain_services.cashier_service,
        )
        FinanceDepartmentToolContextRegistry.register(finance_tool_context)
