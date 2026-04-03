"""财务领域服务装配结果。"""

from dataclasses import dataclass

from accounting.accounting_service import AccountingService
from accounting.sqlite_journal_repository import SQLiteJournalRepository
from cashier.cashier_service import CashierService
from memory.memory_service import MemoryService


@dataclass(frozen=True)
class FinanceDomainServiceBundle:
    """描述会话主链路所需的财务领域服务集合。

    会话装配层需要同时拿到记账、出纳、记忆和部门展示名称等多个对象。把这些对象
    收敛成只读 bundle，可以避免工厂之间继续通过长参数列表相互传递，也让装配边界
    更像正式产品里的组合根，而不是散落的临时变量集合。
    """

    department_display_name: str
    accounting_service: AccountingService
    journal_repository: SQLiteJournalRepository
    cashier_service: CashierService
    memory_service: MemoryService
