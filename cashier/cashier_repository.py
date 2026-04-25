"""出纳/银行仓储接口。"""

from abc import ABC, abstractmethod

from cashier.bank_transaction import BankTransaction
from cashier.query_bank_transactions_query import QueryBankTransactionsQuery
from cashier.record_bank_transaction_command import RecordBankTransactionCommand


class CashierRepository(ABC):
    """定义银行流水存取接口。"""

    @abstractmethod
    def initialize_storage(self) -> None:
        """初始化存储。"""

    @abstractmethod
    def create_transaction(self, command: RecordBankTransactionCommand) -> int:
        """创建银行流水。"""

    @abstractmethod
    def list_transactions(
        self,
        query: QueryBankTransactionsQuery,
    ) -> list[BankTransaction]:
        """查询银行流水。"""

    @abstractmethod
    def get_transaction_by_id(self, transaction_id: int) -> BankTransaction | None:
        """按主键查询银行流水。"""

    @abstractmethod
    def mark_reconciled(
        self,
        transaction_id: int,
        linked_voucher_id: int | None,
    ) -> None:
        """标记银行流水已对账。"""

    @abstractmethod
    def mark_unreconciled(self, transaction_id: int) -> None:
        """解除银行流水对账。"""
