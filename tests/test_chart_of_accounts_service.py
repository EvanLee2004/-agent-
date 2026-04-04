"""会计科目服务测试。"""

import unittest
from dataclasses import dataclass
from typing import Optional

from accounting.account_subject import AccountSubject
from accounting.accounting_error import AccountingError
from accounting.chart_of_accounts_repository import ChartOfAccountsRepository
from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.voucher_draft import VoucherDraft
from accounting.voucher_line_draft import VoucherLineDraft


class FakeChartOfAccountsRepository(ChartOfAccountsRepository):
    """伪造的科目仓储。"""

    def __init__(self, subjects: list[AccountSubject] = None):
        self._subjects = {s.code: s for s in (subjects or [])}

    @property
    def database_path(self) -> str:
        """返回底层数据库路径。"""
        return ":memory:"

    def initialize_storage(self) -> None:
        """初始化存储。"""
        pass

    def save_subjects(self, subjects: list[AccountSubject]) -> None:
        """保存会计科目列表。"""
        for subject in subjects:
            self._subjects[subject.code] = subject

    def list_subjects(self) -> list[AccountSubject]:
        """列出全部科目。"""
        return list(self._subjects.values())

    def get_subject_by_code(self, subject_code: str) -> Optional[AccountSubject]:
        """按编码获取科目。"""
        return self._subjects.get(subject_code)


@dataclass(frozen=True)
class SimpleVoucherLineDraft:
    """简化版凭证分录草稿，仅包含 validate_voucher_subjects 需要的字段。"""

    subject_code: str
    subject_name: str
    debit_amount: float
    credit_amount: float
    description: str


@dataclass(frozen=True)
class SimpleVoucherDraft:
    """简化版凭证草稿，仅用于测试科目校验。"""

    voucher_date: str
    summary: str
    lines: list


class TestChartOfAccountsServiceValidation(unittest.TestCase):
    """科目服务校验测试。"""

    def setUp(self):
        self._repository = FakeChartOfAccountsRepository(
            [
                AccountSubject(
                    "1001", "库存现金", "asset", "debit", "企业持有的现金。"
                ),
                AccountSubject(
                    "1002", "银行存款", "asset", "debit", "企业存放在银行的款项。"
                ),
                AccountSubject(
                    "5001",
                    "主营业务收入",
                    "income",
                    "credit",
                    "企业主营业务形成的收入。",
                ),
            ]
        )
        self._service = ChartOfAccountsService(self._repository)

    def test_validate_voucher_subjects_with_valid_subjects(self):
        """验证使用已注册的科目可以通过校验。"""
        lines = [
            SimpleVoucherLineDraft("1001", "库存现金", 100.0, 0, "提现"),
            SimpleVoucherLineDraft("5001", "主营业务收入", 0, 100.0, "收入"),
        ]
        voucher_draft = SimpleVoucherDraft("2024-03-01", "测试凭证", lines)
        self._service.validate_voucher_subjects(voucher_draft)

    def test_validate_voucher_subjects_subject_not_exists(self):
        """验证使用不存在的科目编码时抛出错误。"""
        lines = [
            SimpleVoucherLineDraft("9999", "不存在的科目", 100.0, 0, "测试"),
        ]
        voucher_draft = SimpleVoucherDraft("2024-03-01", "测试凭证", lines)
        with self.assertRaises(AccountingError) as context:
            self._service.validate_voucher_subjects(voucher_draft)
        self.assertIn("未知会计科目编码: 9999", str(context.exception))

    def test_validate_voucher_subjects_code_name_mismatch(self):
        """验证科目编码与名称不匹配时抛出错误。"""
        lines = [
            SimpleVoucherLineDraft("1001", "银行存款", 100.0, 0, "测试"),
        ]
        voucher_draft = SimpleVoucherDraft("2024-03-01", "测试凭证", lines)
        with self.assertRaises(AccountingError) as context:
            self._service.validate_voucher_subjects(voucher_draft)
        self.assertIn("科目编码与名称不匹配", str(context.exception))


if __name__ == "__main__":
    unittest.main()
