"""本地合成账套测试。"""

import tempfile
import unittest
from pathlib import Path

from accounting.accounting_error import AccountingError
from accounting.accounting_service import AccountingService
from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.query_vouchers_query import QueryVouchersQuery
from accounting.record_voucher_command import RecordVoucherCommand
from accounting.sample_ledger_seeder import SampleLedgerSeeder
from accounting.sqlite_chart_of_accounts_repository import SQLiteChartOfAccountsRepository
from accounting.sqlite_journal_repository import SQLiteJournalRepository
from accounting.voucher_draft import VoucherDraft
from audit.audit_service import AuditService


class SampleLedgerSeederTest(unittest.TestCase):
    """验证确定性账套能生成并覆盖异常场景。"""

    def test_seed_creates_deterministic_small_company_ledger(self):
        """seed 后应产生固定数量凭证并触发审核异常。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "ledger.db")
            chart_repository = SQLiteChartOfAccountsRepository(db_path)
            journal_repository = SQLiteJournalRepository(db_path)
            chart_service = ChartOfAccountsService(chart_repository)
            chart_service.initialize_default_subjects()
            journal_repository.initialize_storage()
            accounting_service = AccountingService(journal_repository, chart_service)
            audit_service = AuditService(journal_repository)

            result = SampleLedgerSeeder(accounting_service, audit_service).seed()
            vouchers = journal_repository.list_vouchers(QueryVouchersQuery(limit=10))

            self.assertEqual(result.voucher_ids, [1, 2, 3, 4, 5])
            self.assertEqual(len(vouchers), 5)
            self.assertTrue(any(voucher.status == "pending" for voucher in vouchers))
            self.assertEqual(len(result.invalid_cases), 1)

            with self.assertRaises(AccountingError):
                accounting_service.record_voucher(
                    RecordVoucherCommand(
                        voucher_draft=VoucherDraft.from_dict(result.invalid_cases[0])
                    )
                )


if __name__ == "__main__":
    unittest.main()
