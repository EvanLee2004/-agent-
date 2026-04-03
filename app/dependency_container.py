"""依赖注入容器。"""

from accounting.accounting_service import AccountingService
from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.query_vouchers_router import QueryVouchersRouter
from accounting.record_voucher_router import RecordVoucherRouter
from accounting.sqlite_chart_of_accounts_repository import SQLiteChartOfAccountsRepository
from accounting.sqlite_journal_repository import SQLiteJournalRepository
from app.application_bootstrapper import ApplicationBootstrapper
from audit.audit_service import AuditService
from audit.audit_voucher_router import AuditVoucherRouter
from configuration.configuration_service import ConfigurationService
from configuration.file_configuration_repository import FileConfigurationRepository
from configuration.llm_configuration import LlmConfiguration
from configuration.provider_catalog import ProviderCatalog
from conversation.deerflow_agent_runtime_repository import DeerFlowAgentRuntimeRepository
from conversation.deerflow_client_factory import DeerFlowClientFactory
from conversation.deerflow_runtime_assets_service import DeerFlowRuntimeAssetsService
from conversation.conversation_router import ConversationRouter
from conversation.conversation_service import ConversationService
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from conversation.tool_use_policy import ToolUsePolicy
from department.finance_department_agent_assets_service import FinanceDepartmentAgentAssetsService
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog
from department.finance_department_tool_context import FinanceDepartmentToolContext
from department.finance_department_tool_context_registry import FinanceDepartmentToolContextRegistry
from memory.markdown_memory_store_repository import MarkdownMemoryStoreRepository
from memory.memory_service import MemoryService
from memory.search_memory_router import SearchMemoryRouter
from memory.sqlite_memory_index_repository import SQLiteMemoryIndexRepository
from memory.store_memory_router import StoreMemoryRouter
from rules.file_rules_repository import FileRulesRepository
from rules.reply_with_rules_router import ReplyWithRulesRouter
from rules.rules_service import RulesService
from tax.calculate_tax_router import CalculateTaxRouter
from tax.tax_service import TaxService


def _build_accounting_stack(
    department_display_name: str,
) -> tuple[AccountingService, SQLiteJournalRepository]:
    """构造账务相关组件。"""
    chart_repository = SQLiteChartOfAccountsRepository()
    journal_repository = SQLiteJournalRepository()
    chart_service = ChartOfAccountsService(chart_repository)
    accounting_service = AccountingService(
        journal_repository,
        chart_service,
        department_display_name,
    )
    return accounting_service, journal_repository


def _build_memory_service(department_display_name: str) -> MemoryService:
    """构造记忆服务。"""
    memory_store_repository = MarkdownMemoryStoreRepository()
    memory_index_repository = SQLiteMemoryIndexRepository()
    return MemoryService(
        memory_store_repository,
        memory_index_repository,
        department_display_name,
    )


def _build_rules_service() -> RulesService:
    """构造规则服务。"""
    return RulesService(FileRulesRepository())


def _build_finance_tool_context(
    accounting_service: AccountingService,
    journal_repository: SQLiteJournalRepository,
    memory_service: MemoryService,
    tool_use_policy: ToolUsePolicy,
    department_display_name: str,
) -> FinanceDepartmentToolContext:
    """构造 DeerFlow 财务工具上下文。

    DeerFlow 的工具是通过 import 路径解析静态对象的，因此本项目需要在
    依赖容器中统一装配 router，再注册到受控上下文注册器。这样做能把
    第三方运行时的约束隔离在容器边界，不让业务服务感知外部框架细节。
    """
    rules_service = _build_rules_service()
    tax_service = TaxService()
    audit_service = AuditService(journal_repository)
    record_voucher_router = RecordVoucherRouter(accounting_service)
    query_vouchers_router = QueryVouchersRouter(accounting_service)
    calculate_tax_router = CalculateTaxRouter(tax_service)
    audit_voucher_router = AuditVoucherRouter(audit_service)
    store_memory_router = StoreMemoryRouter(memory_service)
    search_memory_router = SearchMemoryRouter(memory_service)
    reply_with_rules_router = ReplyWithRulesRouter(
        rules_service,
        memory_service,
        tool_use_policy,
        department_display_name,
    )
    return FinanceDepartmentToolContext(
        record_voucher_router=record_voucher_router,
        query_vouchers_router=query_vouchers_router,
        calculate_tax_router=calculate_tax_router,
        audit_voucher_router=audit_voucher_router,
        store_memory_router=store_memory_router,
        search_memory_router=search_memory_router,
        reply_with_rules_router=reply_with_rules_router,
    )


def _build_conversation_service(
    llm_configuration: LlmConfiguration,
    role_catalog: FinanceDepartmentRoleCatalog,
) -> ConversationService:
    """构造会话服务。"""
    department_display_name = role_catalog.get_department_display_name()
    accounting_service, journal_repository = _build_accounting_stack(
        department_display_name
    )
    memory_service = _build_memory_service(department_display_name)
    tool_use_policy = ToolUsePolicy()
    finance_tool_context = _build_finance_tool_context(
        accounting_service,
        journal_repository,
        memory_service,
        tool_use_policy,
        department_display_name,
    )
    FinanceDepartmentToolContextRegistry.register(finance_tool_context)
    department_agent_assets_service = FinanceDepartmentAgentAssetsService(role_catalog)
    deerflow_runtime_repository = DeerFlowAgentRuntimeRepository(
        configuration=llm_configuration,
        runtime_assets_service=DeerFlowRuntimeAssetsService(department_agent_assets_service),
        client_factory=DeerFlowClientFactory(),
        agent_name=department_agent_assets_service.get_entry_role_name(),
    )
    return ConversationService(
        deerflow_runtime_repository,
        ReplyTextSanitizer(),
    )


class DependencyContainer:
    """依赖注入容器。"""

    def __init__(self, llm_configuration: LlmConfiguration):
        self._llm_configuration = llm_configuration
        self._role_catalog = FinanceDepartmentRoleCatalog()

    def build_conversation_router(self) -> ConversationRouter:
        """构造会话入口。"""
        conversation_service = _build_conversation_service(
            self._llm_configuration,
            self._role_catalog,
        )
        return ConversationRouter(conversation_service)

    def build_application_bootstrapper(self) -> ApplicationBootstrapper:
        """构造引导器。"""
        chart_repository = SQLiteChartOfAccountsRepository()
        journal_repository = SQLiteJournalRepository()
        chart_service = ChartOfAccountsService(chart_repository)
        return ApplicationBootstrapper(chart_repository, journal_repository, chart_service)

    def build_configuration_service(self) -> ConfigurationService:
        """构造配置服务。"""
        return ConfigurationService(FileConfigurationRepository(), ProviderCatalog())

    @staticmethod
    def create_configuration_service() -> ConfigurationService:
        """构造独立配置服务。

        Returns:
            CLI 启动阶段可直接使用的配置服务。
        """
        return ConfigurationService(FileConfigurationRepository(), ProviderCatalog())
