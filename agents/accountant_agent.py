"""智能会计主 Agent。

当前版本的主流程已经切换为：
1. 通过 `SkillPromptService` 构造全局领域上下文
2. 通过 `ToolRuntime` 驱动原生 function calling
3. 通过确定性 Service 执行记账、查账、税务、审核和记忆操作

设计边界：
- Agent 只做编排，不直接处理数据库细节
- skills 只负责领域提示，不再承担 JSON 协议主通道
- 工具执行结果统一回灌给模型，由模型生成最终用户答复
"""

from typing import Optional

from infrastructure.accounting_repository import (
    IChartOfAccountsRepository,
    IJournalRepository,
    get_chart_of_accounts_repository,
    get_journal_repository,
)
from infrastructure.llm import LLMClient
from infrastructure.memory import IAgentMemoryStore, get_memory_store
from infrastructure.skill_loader import SkillLoader
from services.accounting_service import AccountingService
from services.audit_service import AuditService
from services.chart_of_accounts_service import ChartOfAccountsService
from services.memory_service import MemoryService
from services.skill_prompt_service import SkillPromptService
from services.tax_service import TaxService
from services.voucher_service import VoucherService
from tools.handlers import build_default_tool_registry
from tools.registry import ToolRegistry
from tools.runtime import ToolRuntime


class AccountantAgent:
    """智能会计 Agent。"""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        journal_repository: Optional[IJournalRepository] = None,
        chart_repository: Optional[IChartOfAccountsRepository] = None,
        memory_store: Optional[IAgentMemoryStore] = None,
        skill_loader: Optional[SkillLoader] = None,
        chart_of_accounts_service: Optional[ChartOfAccountsService] = None,
        voucher_service: Optional[VoucherService] = None,
        accounting_service: Optional[AccountingService] = None,
        tax_service: Optional[TaxService] = None,
        audit_service: Optional[AuditService] = None,
        prompt_service: Optional[SkillPromptService] = None,
        memory_service: Optional[MemoryService] = None,
        tool_registry: Optional[ToolRegistry] = None,
        tool_runtime: Optional[ToolRuntime] = None,
        agent_name: str = "智能会计",
    ):
        self._llm_client = llm_client
        self._journal_repository = journal_repository or get_journal_repository()
        self._chart_repository = chart_repository or get_chart_of_accounts_repository()
        self._memory_store = memory_store or get_memory_store()
        self._skill_loader = skill_loader or SkillLoader()
        self._agent_name = agent_name

        self._chart_of_accounts_service = chart_of_accounts_service or ChartOfAccountsService(
            repository=self._chart_repository
        )
        self._voucher_service = voucher_service or VoucherService(
            journal_repository=self._journal_repository
        )
        self._accounting_service = accounting_service or AccountingService(
            journal_repository=self._journal_repository,
            chart_of_accounts_service=self._chart_of_accounts_service,
            recorded_by=self._agent_name,
        )
        self._tax_service = tax_service or TaxService()
        self._audit_service = audit_service or AuditService(
            voucher_service=self._voucher_service
        )
        self._prompt_service = prompt_service or SkillPromptService(
            skill_loader=self._skill_loader,
            memory_store=self._memory_store,
            chart_of_accounts_service=self._chart_of_accounts_service,
            agent_name=self._agent_name,
        )
        self._memory_service = memory_service
        self._tool_registry = tool_registry
        self._tool_runtime = tool_runtime

    @property
    def llm_client(self) -> LLMClient:
        """获取 LLM 客户端。"""
        if self._llm_client is None:
            self._llm_client = LLMClient.get_instance()
        return self._llm_client

    @property
    def memory_service(self) -> MemoryService:
        """获取记忆应用服务。"""
        if self._memory_service is None:
            self._memory_service = MemoryService(
                memory_store=self._memory_store,
                agent_name=self._agent_name,
            )
        return self._memory_service

    @property
    def tool_registry(self) -> ToolRegistry:
        """获取默认工具注册表。"""
        if self._tool_registry is None:
            self._tool_registry = build_default_tool_registry(
                accounting_service=self._accounting_service,
                tax_service=self._tax_service,
                audit_service=self._audit_service,
                memory_service=self.memory_service,
                prompt_service=self._prompt_service,
            )
        return self._tool_registry

    @property
    def tool_runtime(self) -> ToolRuntime:
        """获取工具运行时。"""
        if self._tool_runtime is None:
            self._tool_runtime = ToolRuntime(
                llm_client=self.llm_client,
                tool_registry=self.tool_registry,
            )
        return self._tool_runtime

    async def handle(self, user_input: str) -> str:
        """处理用户输入。"""
        try:
            result = self.tool_runtime.run(
                user_input=user_input,
                system_prompt=self._prompt_service.build_agent_tool_prompt(user_input),
            )
            return result.final_reply
        except RuntimeError as exc:
            return f"服务暂时不可用，请稍后重试。({str(exc)})"
