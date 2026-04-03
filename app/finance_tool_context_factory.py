"""财务工具上下文工厂。"""

from accounting.accounting_service import AccountingService
from accounting.query_vouchers_router import QueryVouchersRouter
from accounting.record_voucher_router import RecordVoucherRouter
from accounting.sqlite_journal_repository import SQLiteJournalRepository
from audit.audit_service import AuditService
from audit.audit_voucher_router import AuditVoucherRouter
from cashier.cashier_service import CashierService
from cashier.query_cash_transactions_router import QueryCashTransactionsRouter
from cashier.record_cash_transaction_router import RecordCashTransactionRouter
from conversation.tool_use_policy import ToolUsePolicy
from department.collaboration.collaborate_with_department_role_router import CollaborateWithDepartmentRoleRouter
from department.collaboration.department_collaboration_service import DepartmentCollaborationService
from memory.memory_service import MemoryService
from memory.search_memory_router import SearchMemoryRouter
from memory.store_memory_router import StoreMemoryRouter
from rules.file_rules_repository import FileRulesRepository
from rules.reply_with_rules_router import ReplyWithRulesRouter
from rules.rules_service import RulesService
from runtime.deerflow.finance_department_tool_context import FinanceDepartmentToolContext
from tax.calculate_tax_router import CalculateTaxRouter
from tax.tax_service import TaxService


class FinanceToolContextFactory:
    """负责构造 DeerFlow 可见的财务工具上下文。

    DeerFlow 的工具通过静态模块路径解析，无法像普通应用层那样按请求动态注入。
    这个工厂把所有工具路由装配集中起来，是为了把第三方运行时的特殊约束隔离到
    一个地方，避免依赖容器继续膨胀成系统耦合中心。
    """

    def build(
        self,
        accounting_service: AccountingService,
        journal_repository: SQLiteJournalRepository,
        cashier_service: CashierService,
        memory_service: MemoryService,
        tool_use_policy: ToolUsePolicy,
        department_display_name: str,
        collaboration_service: DepartmentCollaborationService,
    ) -> FinanceDepartmentToolContext:
        """构造财务工具上下文。

        Args:
            accounting_service: 记账服务。
            journal_repository: 凭证仓储。
            cashier_service: 出纳服务。
            memory_service: 记忆服务。
            tool_use_policy: 工具使用策略。
            department_display_name: 部门展示名称。
            collaboration_service: 部门协作服务。

        Returns:
            DeerFlow 工具可消费的统一上下文。
        """
        return FinanceDepartmentToolContext(
            record_voucher_router=RecordVoucherRouter(accounting_service),
            query_vouchers_router=QueryVouchersRouter(accounting_service),
            calculate_tax_router=CalculateTaxRouter(TaxService()),
            audit_voucher_router=AuditVoucherRouter(AuditService(journal_repository)),
            record_cash_transaction_router=RecordCashTransactionRouter(cashier_service),
            query_cash_transactions_router=QueryCashTransactionsRouter(cashier_service),
            store_memory_router=StoreMemoryRouter(memory_service),
            search_memory_router=SearchMemoryRouter(memory_service),
            reply_with_rules_router=self._build_reply_with_rules_router(
                memory_service,
                tool_use_policy,
                department_display_name,
            ),
            collaborate_with_department_role_router=CollaborateWithDepartmentRoleRouter(
                collaboration_service
            ),
        )

    def _build_reply_with_rules_router(
        self,
        memory_service: MemoryService,
        tool_use_policy: ToolUsePolicy,
        department_display_name: str,
    ) -> ReplyWithRulesRouter:
        """构造规则问答工具入口。

        规则问答依赖文件规则仓储，但这些依赖只服务于单个工具族。把它单独封装出来，
        是为了避免 `build(...)` 方法继续增长，也让后续如果规则来源从文件迁到数据库
        或知识库时，只改这一处即可。
        """
        rules_service = RulesService(FileRulesRepository())
        return ReplyWithRulesRouter(
            rules_service,
            memory_service,
            tool_use_policy,
            department_display_name,
        )
