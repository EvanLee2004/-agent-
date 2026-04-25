"""生产级账务内核测试。"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from accounting.accounting_error import AccountingError
from accounting.accounting_service import AccountingService
from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.record_voucher_command import RecordVoucherCommand
from accounting.reverse_voucher_command import ReverseVoucherCommand
from accounting.sqlite_chart_of_accounts_repository import SQLiteChartOfAccountsRepository
from accounting.sqlite_journal_repository import SQLiteJournalRepository
from accounting.voucher_draft import VoucherDraft
from app.application_bootstrapper_factory import ApplicationBootstrapperFactory
from audit.audit_request import AuditRequest
from audit.audit_service import AuditService
from audit.audit_target import AuditTarget
from audit.audit_voucher_command import AuditVoucherCommand
from cashier.sqlite_cashier_repository import SQLiteCashierRepository
from configuration.schema_migration_service import SchemaMigrationService


def _build_service_with_journal(
    tmpdir: str,
) -> tuple[AccountingService, SQLiteJournalRepository]:
    """构造测试用会计服务并返回底层仓储。

    部分生产级测试需要验证“关闭期间后底层状态更新也被拒绝”这类跨服务边界，
    因此这里显式返回仓储给 AuditService 使用，避免测试访问 AccountingService
    的私有成员。
    """
    database_path = str(Path(tmpdir) / "ledger.db")
    journal_repository = SQLiteJournalRepository(database_path)
    chart_repository = SQLiteChartOfAccountsRepository(database_path)
    cashier_repository = SQLiteCashierRepository(database_path)
    ApplicationBootstrapperFactory().build(
        chart_repository,
        journal_repository,
        cashier_repository,
    ).initialize()
    return (
        AccountingService(
            journal_repository,
            ChartOfAccountsService(chart_repository),
        ),
        journal_repository,
    )


def _build_service(tmpdir: str) -> AccountingService:
    """构造测试用会计服务。"""
    service, _journal_repository = _build_service_with_journal(tmpdir)
    return service


def _record_income(service: AccountingService, amount: float = 100) -> int:
    """记录一张销售收入凭证。"""
    return service.record_voucher(
        RecordVoucherCommand(
            VoucherDraft.from_dict(
                {
                    "voucher_date": "2026-04-01",
                    "summary": "销售收入",
                    "lines": [
                        {
                            "subject_code": "1002",
                            "subject_name": "银行存款",
                            "debit_amount": amount,
                            "credit_amount": 0,
                            "description": "收款",
                        },
                        {
                            "subject_code": "5001",
                            "subject_name": "主营业务收入",
                            "debit_amount": 0,
                            "credit_amount": amount,
                            "description": "确认收入",
                        },
                    ],
                }
            )
        )
    )


class AccountingProductionCoreTest(unittest.TestCase):
    """验证期间、生命周期、报表和迁移。"""

    def test_period_sequence_survives_restart_and_closed_period_rejects_recording(self):
        """凭证编号按期间连续，重启后继续递增，已结账期间拒绝写入。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = _build_service(tmpdir)
            first_id = _record_income(service, 100)
            second_id = _record_income(service, 200)

            self.assertEqual(service.get_voucher(first_id).voucher_number, "JV-202604-0001")
            self.assertEqual(service.get_voucher(second_id).voucher_number, "JV-202604-0002")

            restarted_service = _build_service(tmpdir)
            third_id = _record_income(restarted_service, 300)
            self.assertEqual(
                restarted_service.get_voucher(third_id).voucher_number,
                "JV-202604-0003",
            )

            restarted_service.close_period("202604")
            with self.assertRaises(AccountingError):
                _record_income(restarted_service, 400)

    def test_closed_period_rejects_status_updates(self):
        """已结账期间不仅拒绝新增，也拒绝审核等状态修改。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service, journal_repository = _build_service_with_journal(tmpdir)
            voucher_id = _record_income(service, 100)

            service.close_period("202604")

            with self.assertRaises(AccountingError):
                AuditService(journal_repository).audit_voucher(
                    AuditVoucherCommand(
                        audit_request=AuditRequest(
                            target=AuditTarget.VOUCHER_ID,
                            voucher_id=voucher_id,
                        )
                    )
                )

    def test_posted_reports_and_reversal_offset_balances(self):
        """报表只统计已过账凭证，红冲后科目余额自然抵减。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = _build_service(tmpdir)
            voucher_id = _record_income(service, 100)

            service.post_voucher(voucher_id)
            balances = service.list_account_balances("202604")
            self.assertEqual(
                {row.subject_code: row.balance_amount for row in balances},
                {"1002": 100.0, "5001": 100.0},
            )

            reversal = service.reverse_voucher(
                ReverseVoucherCommand(voucher_id=voucher_id, reversal_date="2026-04-02")
            )
            self.assertEqual(reversal.lifecycle_action, "reversal")
            balances_after_reversal = service.list_account_balances("202604")
            self.assertEqual(
                {row.subject_code: row.balance_amount for row in balances_after_reversal},
                {"1002": 0.0, "5001": 0.0},
            )
            trial_balance = service.build_trial_balance("202604")
            self.assertTrue(trial_balance.balanced)

    def test_schema_migration_backfills_old_database_idempotently(self):
        """旧库迁移应补齐期间、生命周期字段和期间内凭证号。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = str(Path(tmpdir) / "legacy.db")
            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    """
                    CREATE TABLE journal_voucher (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        voucher_number TEXT UNIQUE,
                        voucher_date TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        source_text TEXT DEFAULT '',
                        recorded_by TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        reviewed_by TEXT,
                        anomaly_flag TEXT,
                        anomaly_reason TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE journal_line (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        voucher_id INTEGER NOT NULL,
                        line_no INTEGER NOT NULL,
                        subject_code TEXT NOT NULL,
                        subject_name TEXT NOT NULL,
                        debit_amount REAL NOT NULL DEFAULT 0,
                        credit_amount REAL NOT NULL DEFAULT 0,
                        description TEXT DEFAULT ''
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO journal_voucher (
                        voucher_number, voucher_date, summary, source_text, recorded_by
                    )
                    VALUES ('JV-20260401-00001', '2026-04-01', '销售收入', '', '旧系统')
                    """
                )
                connection.commit()

            migration_service = SchemaMigrationService(database_path)
            migration_service.migrate()
            migration_service.migrate()

            with sqlite3.connect(database_path) as connection:
                columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(journal_voucher)"
                    ).fetchall()
                }
                row = connection.execute(
                    """
                    SELECT period_name, voucher_sequence, voucher_number
                    FROM journal_voucher
                    WHERE id = 1
                    """
                ).fetchone()
                migration_count = connection.execute(
                    "SELECT COUNT(*) FROM schema_migrations WHERE version = 2"
                ).fetchone()[0]
                index_names = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA index_list(journal_voucher)"
                    ).fetchall()
                }

            self.assertIn("period_name", columns)
            self.assertIn("lifecycle_action", columns)
            self.assertEqual(row, ("202604", 1, "JV-202604-0001"))
            self.assertEqual(migration_count, 1)
            self.assertIn("ux_journal_voucher_period_sequence", index_names)


if __name__ == "__main__":
    unittest.main()
