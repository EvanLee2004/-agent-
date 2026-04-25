"""出纳/银行服务。"""

from accounting.journal_repository import JournalRepository
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

    def __init__(
        self,
        cashier_repository: CashierRepository,
        journal_repository: JournalRepository | None = None,
    ):
        self._cashier_repository = cashier_repository
        self._journal_repository = journal_repository

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
        current = self._cashier_repository.get_transaction_by_id(command.transaction_id)
        if current is None:
            raise CashierError(f"银行流水 {command.transaction_id} 不存在")
        if current.status == "reconciled":
            if current.linked_voucher_id == command.linked_voucher_id:
                return current
            raise CashierError("已对账流水不能重复关联其他凭证，请先解除对账")
        if command.linked_voucher_id is not None:
            self._validate_linked_voucher(command.linked_voucher_id)
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

    def unreconcile_transaction(self, transaction_id: int) -> BankTransaction:
        """解除银行流水对账。

        Args:
            transaction_id: 银行流水 ID。

        Returns:
            更新后的银行流水。
        """
        if transaction_id <= 0:
            raise CashierError("transaction_id 必须大于 0")
        self._cashier_repository.mark_unreconciled(transaction_id)
        transaction = self._cashier_repository.get_transaction_by_id(transaction_id)
        if transaction is None:
            raise CashierError(f"银行流水 {transaction_id} 不存在")
        return transaction

    def build_voucher_suggestion(self, transaction_id: int) -> dict:
        """根据银行流水生成待入账凭证建议。

        该方法只生成建议，不写入总账。真正入账仍必须走会计凭证工具，
        从而保持出纳和总账的职责边界。
        """
        transaction = self._cashier_repository.get_transaction_by_id(transaction_id)
        if transaction is None:
            raise CashierError(f"银行流水 {transaction_id} 不存在")
        if transaction.direction == "inflow":
            lines = [
                {
                    "subject_code": "1002",
                    "subject_name": "银行存款",
                    "debit_amount": transaction.amount,
                    "credit_amount": 0,
                    "description": transaction.summary,
                },
                {
                    "subject_code": "5001",
                    "subject_name": "主营业务收入",
                    "debit_amount": 0,
                    "credit_amount": transaction.amount,
                    "description": transaction.counterparty,
                },
            ]
        else:
            lines = [
                {
                    "subject_code": "6602",
                    "subject_name": "管理费用",
                    "debit_amount": transaction.amount,
                    "credit_amount": 0,
                    "description": transaction.summary,
                },
                {
                    "subject_code": "1002",
                    "subject_name": "银行存款",
                    "debit_amount": 0,
                    "credit_amount": transaction.amount,
                    "description": transaction.counterparty,
                },
            ]
        return {
            "voucher_date": transaction.transaction_date,
            "summary": transaction.summary,
            "source_text": f"银行流水 {transaction.transaction_id}: {transaction.summary}",
            "lines": lines,
        }

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

    def _validate_linked_voucher(self, voucher_id: int) -> None:
        """校验银行流水关联的凭证必须存在且已过账。"""
        if self._journal_repository is None:
            return
        voucher = self._journal_repository.get_voucher_by_id(voucher_id)
        if voucher is None:
            raise CashierError(f"关联凭证 {voucher_id} 不存在")
        if voucher.status not in ("posted", "reversed"):
            raise CashierError("银行流水只能关联已过账凭证")
