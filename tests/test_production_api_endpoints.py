"""生产级确定性 API 契约测试。"""

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from accounting.accounting_service import AccountingService
from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.record_voucher_command import RecordVoucherCommand
from accounting.sqlite_chart_of_accounts_repository import SQLiteChartOfAccountsRepository
from accounting.sqlite_journal_repository import SQLiteJournalRepository
from accounting.voucher_draft import VoucherDraft
from api.accounting_app import create_app
from app.application_bootstrapper_factory import ApplicationBootstrapperFactory
from cashier.cashier_service import CashierService
from cashier.record_bank_transaction_command import RecordBankTransactionCommand
from cashier.sqlite_cashier_repository import SQLiteCashierRepository


def _build_services(tmpdir: str) -> tuple[AccountingService, CashierService]:
    """构造生产 API 测试服务。"""
    database_path = str(Path(tmpdir) / "ledger.db")
    journal_repository = SQLiteJournalRepository(database_path)
    chart_repository = SQLiteChartOfAccountsRepository(database_path)
    cashier_repository = SQLiteCashierRepository(database_path)
    ApplicationBootstrapperFactory().build(
        chart_repository,
        journal_repository,
        cashier_repository,
    ).initialize()
    accounting_service = AccountingService(
        journal_repository,
        ChartOfAccountsService(chart_repository),
    )
    cashier_service = CashierService(cashier_repository, journal_repository)
    return accounting_service, cashier_service


def _record_income(accounting_service: AccountingService) -> int:
    """记录一张测试收入凭证。"""
    return accounting_service.record_voucher(
        RecordVoucherCommand(
            VoucherDraft.from_dict(
                {
                    "voucher_date": "2026-04-01",
                    "summary": "销售收入",
                    "lines": [
                        {
                            "subject_code": "1002",
                            "subject_name": "银行存款",
                            "debit_amount": 100,
                            "credit_amount": 0,
                        },
                        {
                            "subject_code": "5001",
                            "subject_name": "主营业务收入",
                            "debit_amount": 0,
                            "credit_amount": 100,
                        },
                    ],
                }
            )
        )
    )


class ProductionApiEndpointTest(unittest.TestCase):
    """验证确定性财务 API。"""

    def test_voucher_lifecycle_and_reports(self):
        """过账接口和报表接口应使用同一套账簿事实。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            accounting_service, cashier_service = _build_services(tmpdir)
            voucher_id = _record_income(accounting_service)
            client = TestClient(
                create_app(
                    conversation_handler=None,
                    workbench_service=None,
                    accounting_service=accounting_service,
                    cashier_service=cashier_service,
                )
            )

            posted = client.post(f"/api/accounting/vouchers/{voucher_id}/post")
            trial_balance = client.get(
                "/api/accounting/reports/trial-balance",
                params={"period_name": "202604"},
            )

            self.assertEqual(posted.status_code, 200)
            self.assertEqual(posted.json()["status"], "posted")
            self.assertEqual(trial_balance.status_code, 200)
            self.assertTrue(trial_balance.json()["balanced"])
            self.assertEqual(trial_balance.json()["debit_total"], 100.0)

    def test_error_response_is_structured(self):
        """业务 API 错误应返回统一结构。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            accounting_service, cashier_service = _build_services(tmpdir)
            client = TestClient(
                create_app(
                    accounting_service=accounting_service,
                    cashier_service=cashier_service,
                )
            )

            response = client.post("/api/accounting/periods/202613/open")

            self.assertEqual(response.status_code, 400)
            data = response.json()
            self.assertEqual(data["error_code"], "ACCOUNTING_ERROR")
            self.assertIn("request_id", data)

    def test_validation_error_response_is_structured(self):
        """参数校验错误也应返回统一结构。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            accounting_service, cashier_service = _build_services(tmpdir)
            client = TestClient(
                create_app(
                    accounting_service=accounting_service,
                    cashier_service=cashier_service,
                )
            )

            response = client.post("/api/accounting/vouchers/not-an-int/post")

            self.assertEqual(response.status_code, 422)
            data = response.json()
            self.assertEqual(data["error_code"], "VALIDATION_ERROR")
            self.assertIn("request_id", data)
            self.assertIn("errors", data["details"])

    def test_bank_reconcile_and_suggestion_endpoints(self):
        """银行对账和入账建议接口应可用。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            accounting_service, cashier_service = _build_services(tmpdir)
            voucher_id = _record_income(accounting_service)
            accounting_service.post_voucher(voucher_id)
            transaction_id = cashier_service.record_transaction(
                RecordBankTransactionCommand(
                    transaction_date="2026-04-01",
                    direction="inflow",
                    amount=100,
                    account_name="基本户",
                    counterparty="客户A",
                    summary="收到货款",
                )
            )
            client = TestClient(
                create_app(
                    accounting_service=accounting_service,
                    cashier_service=cashier_service,
                )
            )

            reconciled = client.post(
                f"/api/accounting/bank-transactions/{transaction_id}/reconcile",
                json={"linked_voucher_id": voucher_id},
            )
            suggestion = client.get(
                f"/api/accounting/bank-transactions/{transaction_id}/voucher-suggestion"
            )

            self.assertEqual(reconciled.status_code, 200)
            self.assertEqual(reconciled.json()["status"], "reconciled")
            self.assertEqual(suggestion.status_code, 200)
            self.assertEqual(
                suggestion.json()["suggested_voucher"]["lines"][0]["subject_code"],
                "1002",
            )


if __name__ == "__main__":
    unittest.main()
