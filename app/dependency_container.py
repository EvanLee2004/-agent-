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
from conversation.conversation_router import ConversationRouter
from conversation.conversation_service import ConversationService
from conversation.file_prompt_skill_repository import FilePromptSkillRepository
from conversation.prompt_context_service import PromptContextService
from conversation.tool_loop_service import ToolLoopService
from conversation.tool_router_catalog import ToolRouterCatalog
from conversation.tool_use_policy import ToolUsePolicy
from llm.openai_compatible_llm_chat_repository import OpenAiCompatibleLlmChatRepository
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


def _build_accounting_stack(agent_name: str) -> tuple[ChartOfAccountsService, AccountingService, SQLiteJournalRepository]:
    """构造账务相关组件。"""
    chart_repository = SQLiteChartOfAccountsRepository()
    journal_repository = SQLiteJournalRepository()
    chart_service = ChartOfAccountsService(chart_repository)
    accounting_service = AccountingService(journal_repository, chart_service, agent_name)
    return chart_service, accounting_service, journal_repository


def _build_memory_service(agent_name: str) -> MemoryService:
    """构造记忆服务。"""
    memory_store_repository = MarkdownMemoryStoreRepository()
    memory_index_repository = SQLiteMemoryIndexRepository()
    return MemoryService(memory_store_repository, memory_index_repository, agent_name)


def _build_rules_service(prompt_skill_repository: FilePromptSkillRepository) -> RulesService:
    """构造规则服务。"""
    return RulesService(FileRulesRepository(prompt_skill_repository))


def _build_tool_router_catalog(
    accounting_service: AccountingService,
    tax_service: TaxService,
    audit_service: AuditService,
    memory_service: MemoryService,
    rules_service: RulesService,
    tool_use_policy: ToolUsePolicy,
    agent_name: str,
) -> ToolRouterCatalog:
    """构造工具路由目录。"""
    return ToolRouterCatalog(
        _build_tool_routers(
            accounting_service,
            tax_service,
            audit_service,
            memory_service,
            rules_service,
            tool_use_policy,
            agent_name,
        )
    )


def _build_tool_routers(
    accounting_service: AccountingService,
    tax_service: TaxService,
    audit_service: AuditService,
    memory_service: MemoryService,
    rules_service: RulesService,
    tool_use_policy: ToolUsePolicy,
    agent_name: str,
) -> list:
    """构造工具路由实例列表。"""
    return [
        RecordVoucherRouter(accounting_service),
        QueryVouchersRouter(accounting_service),
        CalculateTaxRouter(tax_service),
        AuditVoucherRouter(audit_service),
        StoreMemoryRouter(memory_service),
        SearchMemoryRouter(memory_service),
        ReplyWithRulesRouter(rules_service, memory_service, tool_use_policy, agent_name),
    ]


def _build_prompt_context_service(
    prompt_skill_repository: FilePromptSkillRepository,
    memory_service: MemoryService,
    chart_service: ChartOfAccountsService,
    tool_use_policy: ToolUsePolicy,
    agent_name: str,
) -> PromptContextService:
    """构造 prompt 上下文服务。"""
    return PromptContextService(
        prompt_skill_repository,
        memory_service,
        chart_service,
        tool_use_policy,
        agent_name,
    )


def _build_conversation_service(
    llm_configuration: LlmConfiguration,
    agent_name: str,
) -> ConversationService:
    """构造会话服务。"""
    chart_service, accounting_service, journal_repository = _build_accounting_stack(agent_name)
    memory_service = _build_memory_service(agent_name)
    prompt_skill_repository = FilePromptSkillRepository()
    tool_use_policy = ToolUsePolicy()
    prompt_context_service = _build_prompt_context_service(
        prompt_skill_repository,
        memory_service,
        chart_service,
        tool_use_policy,
        agent_name,
    )
    tool_router_catalog = _build_conversation_tool_catalog(
        accounting_service,
        journal_repository,
        memory_service,
        prompt_skill_repository,
        tool_use_policy,
        agent_name,
    )
    llm_chat_repository = OpenAiCompatibleLlmChatRepository(llm_configuration)
    return ConversationService(
        prompt_context_service,
        ToolLoopService(llm_chat_repository, tool_router_catalog),
    )


def _build_conversation_tool_catalog(
    accounting_service: AccountingService,
    journal_repository: SQLiteJournalRepository,
    memory_service: MemoryService,
    prompt_skill_repository: FilePromptSkillRepository,
    tool_use_policy: ToolUsePolicy,
    agent_name: str,
) -> ToolRouterCatalog:
    """构造会话场景所需的工具目录。"""
    rules_service = _build_rules_service(prompt_skill_repository)
    return _build_tool_router_catalog(
        accounting_service,
        TaxService(),
        AuditService(journal_repository),
        memory_service,
        rules_service,
        tool_use_policy,
        agent_name,
    )


class DependencyContainer:
    """依赖注入容器。"""

    def __init__(self, llm_configuration: LlmConfiguration, agent_name: str = "智能会计"):
        self._llm_configuration = llm_configuration
        self._agent_name = agent_name

    def build_conversation_router(self) -> ConversationRouter:
        """构造会话入口。"""
        conversation_service = _build_conversation_service(
            self._llm_configuration,
            self._agent_name,
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
