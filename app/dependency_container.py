"""应用服务工厂。

统一创建财务仓储实例，并分别注入到请求处理器和引导器工厂。
这样做有两点好处：
1. 所有仓储复用同一组实例，不会因工厂间各自 new 而产生多份连接；
2. 测试时可以替换为 mock 实例，提升可测试性。
"""

from pathlib import Path
from typing import Optional

from accounting.accounting_service import AccountingService
from accounting.chart_of_accounts_repository import ChartOfAccountsRepository
from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.journal_repository import JournalRepository
from accounting.query_chart_of_accounts_router import QueryChartOfAccountsRouter
from accounting.query_vouchers_router import QueryVouchersRouter
from accounting.record_voucher_router import RecordVoucherRouter
from accounting.sqlite_chart_of_accounts_repository import SQLiteChartOfAccountsRepository
from accounting.sqlite_journal_repository import SQLiteJournalRepository
from app.application_bootstrapper import ApplicationBootstrapper
from app.application_bootstrapper_factory import ApplicationBootstrapperFactory
from app.cli_conversation_handler import CliConversationHandler
from app.conversation_request_handler import AppConversationHandler
from app.department_orchestration_bundle import DepartmentOrchestrationBundle
from app.department_orchestration_factory import DepartmentOrchestrationFactory
from audit.audit_service import AuditService
from audit.audit_voucher_router import AuditVoucherRouter
from cashier.cashier_repository import CashierRepository
from cashier.cashier_service import CashierService
from cashier.query_bank_transactions_router import QueryBankTransactionsRouter
from cashier.reconcile_bank_transaction_router import ReconcileBankTransactionRouter
from cashier.record_bank_transaction_router import RecordBankTransactionRouter
from cashier.sqlite_cashier_repository import SQLiteCashierRepository
from configuration.configuration_service import ConfigurationService
from configuration.file_configuration_repository import FileConfigurationRepository
from configuration.llm_configuration import LlmConfiguration
from configuration.provider_catalog import ProviderCatalog
from conversation.conversation_router import ConversationRouter
from conversation.conversation_service import ConversationService
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from department.accounting_department_service import AccountingDepartmentService
from department.accounting_department_role_catalog import AccountingDepartmentRoleCatalog
from department.workbench.department_workbench_service import DepartmentWorkbenchService
from runtime.crewai.accounting_tool_context import AccountingToolContext


class AppServiceFactory:
    """应用服务工厂。

    统一管理财务仓储、部门编排和请求处理器的创建。

    迁移到 crewAI 后，原来的多层 app 工厂已经没有必要继续保留：会计、审核、
    出纳领域服务、工具上下文和会话路由都只在这里装配一次。把装配收口到本类可以减少样板代码，
    同时仍然保持边界清楚：业务规则在 accounting/audit/cashier，
    crewAI 适配在 runtime/crewai，这里只负责把对象接起来。
    """

    def __init__(
        self,
        llm_configuration: LlmConfiguration,
        runtime_root: Optional[Path] = None,
    ):
        """构造工厂。

        Args:
            llm_configuration: LLM 配置。
            runtime_root: crewAI 运行时根目录。传入独立路径可实现文件路径隔离（API 场景推荐）。
                为 None 时使用 DepartmentOrchestrationFactory 的默认值。
        """
        self._llm_configuration = llm_configuration
        self._role_catalog = AccountingDepartmentRoleCatalog()
        self._runtime_root = runtime_root
        # 延迟创建仓储实例，确保只在真正需要时才初始化
        self._chart_repository: ChartOfAccountsRepository | None = None
        self._journal_repository: JournalRepository | None = None
        self._cashier_repository: CashierRepository | None = None
        # 延迟创建部门编排 bundle，确保 API handler 与历史查询服务共享同一个工作台实例。
        self._orchestration_bundle: DepartmentOrchestrationBundle | None = None

    def _get_repositories(
        self,
    ) -> tuple[
        ChartOfAccountsRepository,
        JournalRepository,
        CashierRepository,
    ]:
        """获取或创建仓储实例。"""
        if self._chart_repository is None:
            self._chart_repository = SQLiteChartOfAccountsRepository()
            self._journal_repository = SQLiteJournalRepository()
            self._cashier_repository = SQLiteCashierRepository()
        return (
            self._chart_repository,
            self._journal_repository,
            self._cashier_repository,
        )

    def _get_or_build_orchestration(self) -> DepartmentOrchestrationBundle:
        """获取或创建部门编排 bundle（延迟初始化）。"""
        if self._orchestration_bundle is None:
            self._orchestration_bundle = DepartmentOrchestrationFactory(
                role_catalog=self._role_catalog,
                configuration=self._llm_configuration,
                runtime_root=self._runtime_root,
            ).build()
        return self._orchestration_bundle

    def build_api_dependencies(
        self,
    ) -> tuple[AppConversationHandler, DepartmentWorkbenchService]:
        """构造 API 所需的全部依赖。

        返回 conversation_handler 和 workbench_service，确保两者共用同一个 bundle 实例。

        Returns:
            (conversation_handler, workbench_service) 元组。
        """
        bundle = self._get_or_build_orchestration()
        conversation_handler = AppConversationHandler(
            self._build_conversation_router(bundle.accounting_department_service),
            self._build_accounting_tool_context(),
        )
        return conversation_handler, bundle.workbench_service

    def build_cli_handler(self) -> CliConversationHandler:
        """构造 CLI 请求处理器。

        返回 CliConversationHandler，异常翻译为用户友好中文文本。
        """
        bundle = self._get_or_build_orchestration()
        return CliConversationHandler(
            self._build_conversation_router(bundle.accounting_department_service),
            self._build_accounting_tool_context(),
        )

    def build_application_bootstrapper(self) -> ApplicationBootstrapper:
        """构造引导器。"""
        chart_repo, journal_repo, cashier_repo = self._get_repositories()
        return ApplicationBootstrapperFactory().build(
            chart_repository=chart_repo,
            journal_repository=journal_repo,
            cashier_repository=cashier_repo,
        )

    def _build_conversation_router(
        self,
        accounting_department_service: AccountingDepartmentService,
    ) -> ConversationRouter:
        """构造纯净会话路由。

        会话层只接收 AccountingDepartmentService 和 ReplyTextSanitizer，不接触
        crewAI 工具上下文。请求作用域仍由 AppConversationHandler/CliConversationHandler
        打开，这样 conversation/ 目录可以继续保持运行时无关。
        """
        return ConversationRouter(
            ConversationService(
                accounting_department_service=accounting_department_service,
                reply_text_sanitizer=ReplyTextSanitizer(),
            )
        )

    def _build_accounting_tool_context(self) -> AccountingToolContext:
        """构造 crewAI 工具可见的会计业务上下文。

        这里直接装配工具路由，而不是再绕一层一次性 factory。原因是当前财务部门
        工具目录仍然很小，显式构造更容易审查依赖边界：写账/查账只依赖 AccountingService，
        审核只依赖 JournalRepository，科目查询只依赖 ChartOfAccountsService，银行流水
        只依赖 CashierService。
        """
        (
            chart_repository,
            journal_repository,
            cashier_repository,
        ) = self._get_repositories()
        chart_service = ChartOfAccountsService(chart_repository)
        accounting_service = AccountingService(
            journal_repository=journal_repository,
            chart_of_accounts_service=chart_service,
            recorded_by=self._role_catalog.get_department_display_name(),
        )
        cashier_service = CashierService(cashier_repository)
        return AccountingToolContext(
            record_voucher_router=RecordVoucherRouter(accounting_service),
            query_vouchers_router=QueryVouchersRouter(accounting_service),
            audit_voucher_router=AuditVoucherRouter(AuditService(journal_repository)),
            query_chart_of_accounts_router=QueryChartOfAccountsRouter(chart_service),
            record_bank_transaction_router=RecordBankTransactionRouter(cashier_service),
            query_bank_transactions_router=QueryBankTransactionsRouter(cashier_service),
            reconcile_bank_transaction_router=ReconcileBankTransactionRouter(
                cashier_service
            ),
        )

    @staticmethod
    def create_configuration_service() -> ConfigurationService:
        """构造独立配置服务。

        Returns:
            CLI 启动阶段可直接使用的配置服务。
        """
        return ConfigurationService(FileConfigurationRepository(), ProviderCatalog())
