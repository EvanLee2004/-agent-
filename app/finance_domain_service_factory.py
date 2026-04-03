"""财务领域服务工厂。"""

from accounting.accounting_service import AccountingService
from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.sqlite_chart_of_accounts_repository import SQLiteChartOfAccountsRepository
from accounting.sqlite_journal_repository import SQLiteJournalRepository
from app.finance_domain_service_bundle import FinanceDomainServiceBundle
from cashier.cashier_service import CashierService
from cashier.sqlite_cashier_repository import SQLiteCashierRepository
from memory.markdown_memory_store_repository import MarkdownMemoryStoreRepository
from memory.memory_service import MemoryService
from memory.sqlite_memory_index_repository import SQLiteMemoryIndexRepository


class FinanceDomainServiceFactory:
    """负责装配财务领域服务。

    记账、出纳和记忆都属于财务业务本身，不应该混进 DeerFlow 运行时或会话边界工厂里。
    单独抽一层领域服务工厂，可以让“业务对象如何组装”与“多 Agent 如何协作”解耦。
    """

    def build(self, department_display_name: str) -> FinanceDomainServiceBundle:
        """构造财务领域服务集合。

        Args:
            department_display_name: 当前产品对外展示的部门名称。

        Returns:
            会话与工具装配需要的财务领域服务 bundle。
        """
        chart_repository = SQLiteChartOfAccountsRepository()
        journal_repository = SQLiteJournalRepository()
        chart_service = ChartOfAccountsService(chart_repository)
        accounting_service = AccountingService(
            journal_repository,
            chart_service,
            department_display_name,
        )
        cashier_service = CashierService(SQLiteCashierRepository())
        memory_service = MemoryService(
            MarkdownMemoryStoreRepository(),
            SQLiteMemoryIndexRepository(),
            department_display_name,
        )
        return FinanceDomainServiceBundle(
            department_display_name=department_display_name,
            accounting_service=accounting_service,
            journal_repository=journal_repository,
            cashier_service=cashier_service,
            memory_service=memory_service,
        )
