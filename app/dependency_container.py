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
from cashier.cashier_service import CashierService
from cashier.query_cash_transactions_router import QueryCashTransactionsRouter
from cashier.record_cash_transaction_router import RecordCashTransactionRouter
from cashier.sqlite_cashier_repository import SQLiteCashierRepository
from configuration.configuration_service import ConfigurationService
from configuration.file_configuration_repository import FileConfigurationRepository
from configuration.llm_configuration import LlmConfiguration
from configuration.provider_catalog import ProviderCatalog
from conversation.deerflow_client_factory import DeerFlowClientFactory
from conversation.deerflow_department_role_runtime_repository import DeerFlowDepartmentRoleRuntimeRepository
from conversation.deerflow_runtime_assets_service import DeerFlowRuntimeAssetsService
from conversation.conversation_router import ConversationRouter
from conversation.conversation_service import ConversationService
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from conversation.tool_use_policy import ToolUsePolicy
from department.collaborate_with_department_role_router import CollaborateWithDepartmentRoleRouter
from department.department_collaboration_service import DepartmentCollaborationService
from department.department_runtime_context import DepartmentRuntimeContext
from department.department_workbench_service import DepartmentWorkbenchService
from department.finance_department_agent_assets_service import FinanceDepartmentAgentAssetsService
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog
from department.finance_department_service import FinanceDepartmentService
from department.finance_department_tool_context import FinanceDepartmentToolContext
from department.finance_department_tool_context_registry import FinanceDepartmentToolContextRegistry
from department.in_memory_department_workbench_repository import InMemoryDepartmentWorkbenchRepository
from department.role_trace_summary_builder import RoleTraceSummaryBuilder
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


def _build_cashier_service(database_path: str = "data/ledger.db") -> tuple[CashierService, SQLiteCashierRepository]:
    """构造出纳服务与仓储。"""
    cashier_repository = SQLiteCashierRepository(database_path)
    return CashierService(cashier_repository), cashier_repository


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
    cashier_service: CashierService,
    memory_service: MemoryService,
    tool_use_policy: ToolUsePolicy,
    department_display_name: str,
    collaboration_service: DepartmentCollaborationService,
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
    record_cash_transaction_router = RecordCashTransactionRouter(cashier_service)
    query_cash_transactions_router = QueryCashTransactionsRouter(cashier_service)
    store_memory_router = StoreMemoryRouter(memory_service)
    search_memory_router = SearchMemoryRouter(memory_service)
    reply_with_rules_router = ReplyWithRulesRouter(
        rules_service,
        memory_service,
        tool_use_policy,
        department_display_name,
    )
    collaborate_with_department_role_router = CollaborateWithDepartmentRoleRouter(
        collaboration_service
    )
    return FinanceDepartmentToolContext(
        record_voucher_router=record_voucher_router,
        query_vouchers_router=query_vouchers_router,
        calculate_tax_router=calculate_tax_router,
        audit_voucher_router=audit_voucher_router,
        record_cash_transaction_router=record_cash_transaction_router,
        query_cash_transactions_router=query_cash_transactions_router,
        store_memory_router=store_memory_router,
        search_memory_router=search_memory_router,
        reply_with_rules_router=reply_with_rules_router,
        collaborate_with_department_role_router=collaborate_with_department_role_router,
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
    cashier_service, _ = _build_cashier_service()
    memory_service = _build_memory_service(department_display_name)
    tool_use_policy = ToolUsePolicy()
    runtime_context = DepartmentRuntimeContext()
    role_trace_summary_builder = RoleTraceSummaryBuilder()
    department_agent_assets_service = FinanceDepartmentAgentAssetsService(role_catalog)
    role_runtime_repository = DeerFlowDepartmentRoleRuntimeRepository(
        configuration=llm_configuration,
        runtime_assets_service=DeerFlowRuntimeAssetsService(department_agent_assets_service),
        client_factory=DeerFlowClientFactory(),
        runtime_context=runtime_context,
        reply_text_sanitizer=ReplyTextSanitizer(),
    )
    workbench_service = DepartmentWorkbenchService(
        InMemoryDepartmentWorkbenchRepository()
    )
    collaboration_service = DepartmentCollaborationService(
        role_catalog=role_catalog,
        runtime_repository=role_runtime_repository,
        workbench_service=workbench_service,
        runtime_context=runtime_context,
        role_trace_summary_builder=role_trace_summary_builder,
    )
    finance_tool_context = _build_finance_tool_context(
        accounting_service,
        journal_repository,
        cashier_service,
        memory_service,
        tool_use_policy,
        department_display_name,
        collaboration_service,
    )
    FinanceDepartmentToolContextRegistry.register(finance_tool_context)
    finance_department_service = FinanceDepartmentService(
        role_catalog=role_catalog,
        role_runtime_repository=role_runtime_repository,
        workbench_service=workbench_service,
        role_trace_summary_builder=role_trace_summary_builder,
    )
    return ConversationService(
        finance_department_service,
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
        cashier_repository = SQLiteCashierRepository()
        chart_service = ChartOfAccountsService(chart_repository)
        return ApplicationBootstrapper(
            chart_repository,
            journal_repository,
            chart_service,
            cashier_repository,
        )

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
