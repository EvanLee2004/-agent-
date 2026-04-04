"""财务领域服务装配结果。"""

from dataclasses import dataclass

from accounting.accounting_service import AccountingService
from accounting.sqlite_journal_repository import SQLiteJournalRepository
from cashier.cashier_service import CashierService


@dataclass(frozen=True)
class FinanceDomainServiceBundle:
    """描述会话主链路所需的财务领域服务集合。

    会话装配层需要同时拿到记账、出纳和部门展示名称等多个对象。把这些对象收敛成只读
    bundle，可以避免工厂之间继续通过长参数列表相互传递，也让装配边界更像正式产品里
    的组合根，而不是散落的临时变量集合。

    记忆服务已从 bundle 中移除：记忆功能切换至 DeerFlow 原生机制，由 DeerFlow 在
    对话层自动管理，不再需要项目层显式持有记忆服务实例。
    """

    department_display_name: str
    accounting_service: AccountingService
    journal_repository: SQLiteJournalRepository
    cashier_service: CashierService
