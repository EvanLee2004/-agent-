"""出纳/银行服务。"""

from cashier.bank_transaction import BankTransaction
from cashier.cashier_error import CashierError
from cashier.cashier_repository import CashierRepository
from cashier.query_bank_transactions_query import QueryBankTransactionsQuery
from cashier.reconcile_bank_transaction_command import ReconcileBankTransactionCommand
from cashier.record_bank_transaction_command import RecordBankTransactionCommand


VALID_DIRECTIONS = {"inflow", "outflow"}
VALID_STATUSES = {"unreconciled", "reconciled"}
MAX_QUERY_LIMIT = 100


class CashierService:
    """处理银行流水记录、查询和对账状态。

    出纳模块只维护资金流水事实，不直接改总账凭证。需要入账时，由会计 Agent
    通过 `record_voucher` 工具生成凭证，保持资金流水和总账事实边界清楚。
    """

    def __init__(self, cashier_repository: CashierRepository):
        self._cashier_repository = cashier_repository

    def record_transaction(self, command: RecordBankTransactionCommand) -> int:
        """记录银行流水。

        Args:
            command: 银行流水记录命令。

        Returns:
            新建银行流水主键。

        Raises:
            CashierError: 流水方向、金额或必要文本字段不合法时抛出。
        """
        self._validate_record_command(command)
        return self._cashier_repository.create_transaction(command)

    def query_transactions(
        self,
        query: QueryBankTransactionsQuery,
    ) -> list[BankTransaction]:
        """查询银行流水。

        Args:
            query: 银行流水查询条件。

        Returns:
            满足条件的银行流水列表。

        Raises:
            CashierError: 过滤条件不在当前受控取值范围内时抛出。
        """
        self._validate_query(query)
        return self._cashier_repository.list_transactions(query)

    def reconcile_transaction(
        self,
        command: ReconcileBankTransactionCommand,
    ) -> BankTransaction:
        """标记银行流水已对账并返回更新后的记录。

        Args:
            command: 银行流水对账命令。

        Returns:
            更新后的银行流水。

        Raises:
            CashierError: 流水不存在或 ID 不合法时抛出。
        """
        if command.transaction_id <= 0:
            raise CashierError("transaction_id 必须大于 0")
        self._cashier_repository.mark_reconciled(
            transaction_id=command.transaction_id,
            linked_voucher_id=command.linked_voucher_id,
        )
        transaction = self._cashier_repository.get_transaction_by_id(
            command.transaction_id
        )
        if transaction is None:
            raise CashierError(f"银行流水 {command.transaction_id} 不存在")
        return transaction

    def _validate_record_command(self, command: RecordBankTransactionCommand) -> None:
        """校验银行流水记录命令。"""
        if not command.transaction_date.strip():
            raise CashierError("transaction_date 不能为空")
        if command.direction not in VALID_DIRECTIONS:
            raise CashierError("direction 只能是 inflow 或 outflow")
        if command.amount <= 0:
            raise CashierError("amount 必须大于 0")
        if not command.account_name.strip():
            raise CashierError("account_name 不能为空")
        if not command.summary.strip():
            raise CashierError("summary 不能为空")

    def _validate_query(self, query: QueryBankTransactionsQuery) -> None:
        """校验银行流水查询条件。

        查询工具不产生副作用，但仍要限制输入范围。这样可以避免 Agent 传入
        负数 limit、未知状态或未知方向后把异常抛到 runtime 外层。
        """
        if query.direction and query.direction not in VALID_DIRECTIONS:
            raise CashierError("direction 只能是 inflow 或 outflow")
        if query.status and query.status not in VALID_STATUSES:
            raise CashierError("status 只能是 unreconciled 或 reconciled")
        if query.limit <= 0 or query.limit > MAX_QUERY_LIMIT:
            raise CashierError("limit 必须在 1 到 100 之间")
