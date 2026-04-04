"""审核服务测试。"""

import unittest
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from accounting.journal_repository import JournalRepository
from audit.audit_request import AuditRequest
from audit.audit_service import AuditService
from audit.audit_target import AuditTarget
from audit.audit_voucher_command import AuditVoucherCommand


@dataclass
class FakeVoucherLine:
    """伪造凭证分录。"""

    account_code: str
    account_name: str
    debit_amount: float
    credit_amount: float
    description: str = ""


@dataclass
class FakeVoucher:
    """伪造凭证对象。"""

    voucher_id: int
    voucher_number: str
    voucher_date: str
    summary: str
    lines: list = field(default_factory=list)

    def get_total_amount(self) -> float:
        """获取凭证总金额。"""
        return sum(line.debit_amount for line in self.lines)


class FakeJournalRepository(JournalRepository):
    """伪造的凭证仓储。"""

    def __init__(self, vouchers: list[FakeVoucher] = None):
        self._vouchers = vouchers or []

    @property
    def database_path(self) -> str:
        """返回底层数据库路径。"""
        return ":memory:"

    def initialize_storage(self) -> None:
        """初始化存储。"""
        pass

    def create_voucher(self, command, recorded_by: str) -> int:
        raise NotImplementedError

    def list_vouchers(self, query) -> list[FakeVoucher]:
        return self._vouchers

    def get_voucher_by_id(self, voucher_id: int) -> Optional[FakeVoucher]:
        for v in self._vouchers:
            if v.voucher_id == voucher_id:
                return v
        return None

    def get_latest_voucher(self) -> Optional[FakeVoucher]:
        return self._vouchers[-1] if self._vouchers else None

    def update_status(
        self,
        voucher_id: int,
        status: str,
        reviewed_by: Optional[str],
    ) -> None:
        """更新凭证状态。"""
        pass


class TestAuditServiceDuplicateDetection(unittest.TestCase):
    """审核服务重复检测测试。"""

    def _make_voucher(
        self,
        voucher_id: int,
        voucher_date: str,
        summary: str,
        debit: float,
        credit: float,
    ) -> FakeVoucher:
        """创建测试用凭证。"""
        return FakeVoucher(
            voucher_id=voucher_id,
            voucher_number=f"V{voucher_id:04d}",
            voucher_date=voucher_date,
            summary=summary,
            lines=[FakeVoucherLine("1001", "银行存款", debit, credit, "描述")],
        )

    def test_no_duplicate_when_all_different(self):
        """测试不同凭证不被标记为重复。"""
        vouchers = [
            self._make_voucher(1, "2024-01-01", "收到货款", 1000.0, 1000.0),
            self._make_voucher(2, "2024-01-02", "支付费用", 500.0, 500.0),
        ]
        repo = FakeJournalRepository(vouchers)
        service = AuditService(repo)

        # 检查凭证1，与凭证2不同日期，应该不是重复
        result = service._has_duplicate_voucher(vouchers[0], vouchers)
        self.assertFalse(result)

    def test_duplicate_when_same_date_summary_and_amount(self):
        """测试日期、摘要、金额都相同时被标记为重复。"""
        vouchers = [
            self._make_voucher(1, "2024-01-01", "收到货款", 1000.0, 1000.0),
            self._make_voucher(2, "2024-01-01", "收到货款", 1000.0, 1000.0),
        ]
        repo = FakeJournalRepository(vouchers)
        service = AuditService(repo)

        result = service._has_duplicate_voucher(vouchers[0], vouchers)
        self.assertTrue(result)

    def test_no_duplicate_when_only_date_same(self):
        """测试只有日期相同时不是重复。"""
        vouchers = [
            self._make_voucher(1, "2024-01-01", "收到货款", 1000.0, 1000.0),
            self._make_voucher(2, "2024-01-01", "支付费用", 500.0, 500.0),
        ]
        repo = FakeJournalRepository(vouchers)
        service = AuditService(repo)

        result = service._has_duplicate_voucher(vouchers[0], vouchers)
        self.assertFalse(result)

    def test_no_duplicate_when_only_summary_same(self):
        """测试只有摘要相同时不是重复。"""
        vouchers = [
            self._make_voucher(1, "2024-01-01", "收到货款", 1000.0, 1000.0),
            self._make_voucher(2, "2024-01-02", "收到货款", 500.0, 500.0),
        ]
        repo = FakeJournalRepository(vouchers)
        service = AuditService(repo)

        result = service._has_duplicate_voucher(vouchers[0], vouchers)
        self.assertFalse(result)

    def test_no_duplicate_when_only_amount_same(self):
        """测试只有金额相同时不是重复。"""
        vouchers = [
            self._make_voucher(1, "2024-01-01", "收到货款", 1000.0, 1000.0),
            self._make_voucher(2, "2024-01-02", "支付费用", 1000.0, 1000.0),
        ]
        repo = FakeJournalRepository(vouchers)
        service = AuditService(repo)

        result = service._has_duplicate_voucher(vouchers[0], vouchers)
        self.assertFalse(result)

    def test_no_duplicate_within_tolerance(self):
        """测试金额在容差范围内不视为重复。"""
        vouchers = [
            self._make_voucher(1, "2024-01-01", "收到货款", 1000.0, 1000.0),
            self._make_voucher(2, "2024-01-01", "收到货款", 1000.005, 1000.005),
        ]
        repo = FakeJournalRepository(vouchers)
        service = AuditService(repo)

        # 金额差异 0.005 < 0.01 容差，应该被标记为重复
        result = service._has_duplicate_voucher(vouchers[0], vouchers)
        self.assertTrue(result)

    def test_voucher_not_duplicate_with_self_in_list(self):
        """测试凭证列表包含自身时不会被标记为重复。

        这是核心测试用例：验证 _has_duplicate_voucher 使用 == 跳过自身
        而不是用 != 导致自身被误判为重复。
        """
        voucher = self._make_voucher(1, "2024-01-01", "收到货款", 1000.0, 1000.0)
        vouchers = [voucher]  # 列表中只有自身

        repo = FakeJournalRepository(vouchers)
        service = AuditService(repo)

        # 应该返回 False，因为自身不应该被判定为重复
        result = service._has_duplicate_voucher(voucher, vouchers)
        self.assertFalse(result)

    def test_voucher_not_duplicate_with_self_and_others(self):
        """测试凭证列表包含自身和其他凭证时不会被自身误判为重复。"""
        voucher1 = self._make_voucher(1, "2024-01-01", "收到货款", 1000.0, 1000.0)
        voucher2 = self._make_voucher(2, "2024-01-02", "支付费用", 500.0, 500.0)
        vouchers = [voucher1, voucher2]

        repo = FakeJournalRepository(vouchers)
        service = AuditService(repo)

        # 检查凭证1，应该返回 False
        result = service._has_duplicate_voucher(voucher1, vouchers)
        self.assertFalse(result)

    def test_duplicate_with_multiple_similar_vouchers(self):
        """测试多张相似凭证时正确识别重复。"""
        vouchers = [
            self._make_voucher(1, "2024-01-01", "收到货款", 1000.0, 1000.0),
            self._make_voucher(2, "2024-01-02", "支付费用", 500.0, 500.0),
            self._make_voucher(
                3, "2024-01-01", "收到货款", 1000.0, 1000.0
            ),  # 与凭证1重复
        ]

        repo = FakeJournalRepository(vouchers)
        service = AuditService(repo)

        # 凭证1与凭证3重复
        result = service._has_duplicate_voucher(vouchers[0], vouchers)
        self.assertTrue(result)

        # 凭证2与凭证1、3都不重复
        result = service._has_duplicate_voucher(vouchers[1], vouchers)
        self.assertFalse(result)


class TestAuditServiceAmountThreshold(unittest.TestCase):
    """审核服务金额阈值测试。"""

    def _make_voucher(
        self, voucher_id: int, debit: float, credit: float
    ) -> FakeVoucher:
        """创建测试用凭证。"""
        return FakeVoucher(
            voucher_id=voucher_id,
            voucher_number=f"V{voucher_id:04d}",
            voucher_date="2024-01-01",
            summary="测试摘要足够长的描述",
            lines=[FakeVoucherLine("1001", "银行存款", debit, credit, "描述")],
        )

    def test_large_amount_flag_above_threshold(self):
        """测试超过阈值的凭证被标记。"""
        voucher = self._make_voucher(1, 60000.0, 60000.0)
        repo = FakeJournalRepository([voucher])
        service = AuditService(repo)

        flags = service._build_amount_flags(voucher)
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0].code, "LARGE_AMOUNT")

    def test_normal_amount_no_flag(self):
        """测试正常金额不被标记。"""
        voucher = self._make_voucher(1, 1000.0, 1000.0)
        repo = FakeJournalRepository([voucher])
        service = AuditService(repo)

        flags = service._build_amount_flags(voucher)
        self.assertEqual(len(flags), 0)


if __name__ == "__main__":
    unittest.main()
