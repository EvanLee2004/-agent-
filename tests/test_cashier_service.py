"""出纳/银行服务测试。"""

import tempfile
import unittest
from pathlib import Path

from accounting.accounting_service import AccountingService
from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.record_voucher_command import RecordVoucherCommand
from accounting.sqlite_chart_of_accounts_repository import SQLiteChartOfAccountsRepository
from accounting.sqlite_journal_repository import SQLiteJournalRepository
from accounting.voucher_draft import VoucherDraft
from app.application_bootstrapper_factory import ApplicationBootstrapperFactory
from cashier.cashier_error import CashierError
from cashier.cashier_service import CashierService
from cashier.query_bank_transactions_query import QueryBankTransactionsQuery
from cashier.reconcile_bank_transaction_command import ReconcileBankTransactionCommand
from cashier.record_bank_transaction_command import RecordBankTransactionCommand
from cashier.sqlite_cashier_repository import SQLiteCashierRepository


def _record_posted_voucher(database_path: str, amount: float = 100) -> int:
    """记录并过账一张测试凭证。"""
    journal_repository = SQLiteJournalRepository(database_path)
    chart_repository = SQLiteChartOfAccountsRepository(database_path)
    cashier_repository = SQLiteCashierRepository(database_path)
    ApplicationBootstrapperFactory().build(
        chart_repository,
        journal_repository,
        cashier_repository,
    ).initialize()
    service = AccountingService(
        journal_repository,
        ChartOfAccountsService(chart_repository),
    )
    voucher_id = service.record_voucher(
        RecordVoucherCommand(
            VoucherDraft.from_dict(
                {
                    "voucher_date": "2026-01-01",
                    "summary": "销售收入",
                    "lines": [
                        {
                            "subject_code": "1002",
                            "subject_name": "银行存款",
                            "debit_amount": amount,
                            "credit_amount": 0,
                        },
                        {
                            "subject_code": "5001",
                            "subject_name": "主营业务收入",
                            "debit_amount": 0,
                            "credit_amount": amount,
                        },
                    ],
                }
            )
        )
    )
    service.post_voucher(voucher_id)
    return voucher_id


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

    def test_reconcile_requires_posted_voucher_and_supports_unreconcile(self):
        """银行流水只能关联已过账凭证，重复对账前必须解除。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = str(Path(tmpdir) / "ledger.db")
            voucher_id = _record_posted_voucher(database_path, 100)
            other_voucher_id = _record_posted_voucher(database_path, 200)
            repository = SQLiteCashierRepository(database_path)
            service = CashierService(
                repository,
                SQLiteJournalRepository(database_path),
            )
            transaction_id = service.record_transaction(
                RecordBankTransactionCommand(
                    transaction_date="2026-01-01",
                    direction="inflow",
                    amount=100,
                    account_name="基本户",
                    counterparty="客户A",
                    summary="收到货款",
                )
            )

            reconciled = service.reconcile_transaction(
                ReconcileBankTransactionCommand(
                    transaction_id=transaction_id,
                    linked_voucher_id=voucher_id,
                )
            )
            self.assertEqual(reconciled.status, "reconciled")

            with self.assertRaises(CashierError):
                service.reconcile_transaction(
                    ReconcileBankTransactionCommand(
                        transaction_id=transaction_id,
                        linked_voucher_id=other_voucher_id,
                    )
                )

            unreconciled = service.unreconcile_transaction(transaction_id)
            self.assertEqual(unreconciled.status, "unreconciled")
            rereconciled = service.reconcile_transaction(
                ReconcileBankTransactionCommand(
                    transaction_id=transaction_id,
                    linked_voucher_id=other_voucher_id,
                )
            )
            self.assertEqual(rereconciled.linked_voucher_id, other_voucher_id)

    def test_bank_transaction_suggestion_does_not_record_voucher(self):
        """银行流水入账建议只返回凭证草稿，不写总账。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = str(Path(tmpdir) / "ledger.db")
            repository = SQLiteCashierRepository(database_path)
            repository.initialize_storage()
            service = CashierService(repository)
            transaction_id = service.record_transaction(
                RecordBankTransactionCommand(
                    transaction_date="2026-01-01",
                    direction="outflow",
                    amount=88,
                    account_name="基本户",
                    counterparty="供应商A",
                    summary="支付办公费",
                )
            )

            suggestion = service.build_voucher_suggestion(transaction_id)

            self.assertEqual(suggestion["voucher_date"], "2026-01-01")
            self.assertEqual(suggestion["lines"][0]["subject_code"], "6602")


if __name__ == "__main__":
    unittest.main()
