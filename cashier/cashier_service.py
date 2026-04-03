"""出纳服务。"""

from cashier.cashier_error import CashierError
from cashier.cashier_repository import CashierRepository
from cashier.cash_transaction import CashTransaction
from cashier.query_cash_transactions_query import QueryCashTransactionsQuery
from cashier.record_cash_transaction_command import RecordCashTransactionCommand


ALLOWED_CASH_DIRECTIONS = {"receipt", "payment"}


class CashierService:
    """处理资金收付事实。"""

    def __init__(self, cashier_repository: CashierRepository):
        self._cashier_repository = cashier_repository

    def record_transaction(self, command: RecordCashTransactionCommand) -> int:
        """记录资金收付事实。"""
        self._validate_command(command)
        return self._cashier_repository.create_transaction(command)

    def query_transactions(self, query: QueryCashTransactionsQuery) -> list[CashTransaction]:
        """查询资金收付记录。"""
        return self._cashier_repository.list_transactions(query)

    def _validate_command(self, command: RecordCashTransactionCommand) -> None:
        """校验资金收付命令。"""
        if command.direction not in ALLOWED_CASH_DIRECTIONS:
            raise CashierError("资金方向必须为 receipt 或 payment")
        if command.amount <= 0:
            raise CashierError("资金金额必须大于 0")
        if not command.transaction_date.strip():
            raise CashierError("资金日期不能为空")
        if not command.account_name.strip():
            raise CashierError("资金账户不能为空")
        if not command.summary.strip():
            raise CashierError("资金摘要不能为空")

