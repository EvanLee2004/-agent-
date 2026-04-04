"""出纳仓储接口。"""

from abc import ABC, abstractmethod

from cashier.cash_transaction import CashTransaction
from cashier.query_cash_transactions_query import QueryCashTransactionsQuery
from cashier.record_cash_transaction_command import RecordCashTransactionCommand


class CashierRepository(ABC):
    """定义出纳仓储接口。"""

    @property
    @abstractmethod
    def database_path(self) -> str:
        """返回底层数据库路径。"""

    @abstractmethod
    def initialize_storage(self) -> None:
        """初始化出纳存储。"""

    @abstractmethod
    def create_transaction(self, command: RecordCashTransactionCommand) -> int:
        """新增资金收付记录。"""

    @abstractmethod
    def list_transactions(self, query: QueryCashTransactionsQuery) -> list[CashTransaction]:
        """查询资金收付记录。"""

