"""出纳/银行服务测试。"""

import tempfile
import unittest
from pathlib import Path

from cashier.cashier_error import CashierError
from cashier.cashier_service import CashierService
from cashier.query_bank_transactions_query import QueryBankTransactionsQuery
from cashier.reconcile_bank_transaction_command import ReconcileBankTransactionCommand
from cashier.record_bank_transaction_command import RecordBankTransactionCommand
from cashier.sqlite_cashier_repository import SQLiteCashierRepository


class CashierServiceTest(unittest.TestCase):
    """验证银行流水记录、查询和对账。"""

    def test_record_query_and_reconcile_bank_transaction(self):
        """银行流水可以记录、查询并标记对账。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = SQLiteCashierRepository(str(Path(tmpdir) / "ledger.db"))
            repository.initialize_storage()
            service = CashierService(repository)

            transaction_id = service.record_transaction(
                RecordBankTransactionCommand(
                    transaction_date="2026-01-01",
                    direction="inflow",
                    amount=1000,
                    account_name="基本户",
                    counterparty="客户A",
                    summary="收到货款",
                )
            )
            transactions = service.query_transactions(
                QueryBankTransactionsQuery(status="unreconciled")
            )
            reconciled = service.reconcile_transaction(
                ReconcileBankTransactionCommand(
                    transaction_id=transaction_id,
                    linked_voucher_id=7,
                )
            )

            self.assertEqual(len(transactions), 1)
            self.assertEqual(transactions[0].transaction_id, transaction_id)
            self.assertEqual(reconciled.status, "reconciled")
            self.assertEqual(reconciled.linked_voucher_id, 7)

    def test_rejects_invalid_direction(self):
        """出纳流水方向必须明确。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = SQLiteCashierRepository(str(Path(tmpdir) / "ledger.db"))
            repository.initialize_storage()
            service = CashierService(repository)

            with self.assertRaises(CashierError):
                service.record_transaction(
                    RecordBankTransactionCommand(
                        transaction_date="2026-01-01",
                        direction="bad",
                        amount=100,
                        account_name="基本户",
                        counterparty="客户A",
                        summary="收到货款",
                    )
                )

    def test_rejects_invalid_query_filter(self):
        """银行流水查询过滤条件必须在受控范围内。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = SQLiteCashierRepository(str(Path(tmpdir) / "ledger.db"))
            repository.initialize_storage()
            service = CashierService(repository)

            with self.assertRaises(CashierError):
                service.query_transactions(QueryBankTransactionsQuery(limit=0))

            with self.assertRaises(CashierError):
                service.query_transactions(QueryBankTransactionsQuery(status="bad"))


if __name__ == "__main__":
    unittest.main()
