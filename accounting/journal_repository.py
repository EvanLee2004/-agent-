"""凭证仓储接口。"""

from abc import ABC, abstractmethod
from typing import Optional

from accounting.account_balance import AccountBalance
from accounting.accounting_period import AccountingPeriod
from accounting.journal_voucher import JournalVoucher
from accounting.ledger_entry import LedgerEntry
from accounting.record_voucher_command import RecordVoucherCommand
from accounting.query_vouchers_query import QueryVouchersQuery
from accounting.reverse_voucher_command import ReverseVoucherCommand
from accounting.trial_balance_report import TrialBalanceReport


class JournalRepository(ABC):
    """凭证仓储接口。"""

    @property
    @abstractmethod
    def database_path(self) -> str:
        """返回底层数据库路径。"""
        raise NotImplementedError

    @abstractmethod
    def initialize_storage(self) -> None:
        """初始化存储。

        Raises:
            OSError: 底层存储初始化失败时抛出。
        """
        raise NotImplementedError

    @abstractmethod
    def create_voucher(self, command: RecordVoucherCommand, recorded_by: str) -> int:
        """创建凭证。

        Args:
            command: 记账命令。
            recorded_by: 记账来源。

        Returns:
            新建凭证主键。
        """
        raise NotImplementedError

    @abstractmethod
    def get_voucher_by_id(self, voucher_id: int) -> Optional[JournalVoucher]:
        """按主键读取凭证。

        Args:
            voucher_id: 凭证主键。

        Returns:
            对应凭证；不存在时返回 `None`。
        """
        raise NotImplementedError

    @abstractmethod
    def get_latest_voucher(self) -> Optional[JournalVoucher]:
        """读取最新凭证。

        Returns:
            最新凭证；不存在时返回 `None`。
        """
        raise NotImplementedError

    @abstractmethod
    def list_vouchers(self, query: QueryVouchersQuery) -> list[JournalVoucher]:
        """列出凭证。

        Args:
            query: 查询条件。

        Returns:
            满足条件的凭证列表。
        """
        raise NotImplementedError

    @abstractmethod
    def update_status(
        self,
        voucher_id: int,
        status: str,
        reviewed_by: Optional[str],
    ) -> None:
        """更新凭证状态。

        Args:
            voucher_id: 凭证主键。
            status: 新状态。
            reviewed_by: 审核人。
        """
        raise NotImplementedError

    def list_periods(self) -> list[AccountingPeriod]:
        """列出全部会计期间。"""
        raise NotImplementedError

    def open_period(self, period_name: str) -> AccountingPeriod:
        """打开或创建会计期间。"""
        raise NotImplementedError

    def close_period(self, period_name: str) -> AccountingPeriod:
        """关闭会计期间。"""
        raise NotImplementedError

    def post_voucher(self, voucher_id: int) -> JournalVoucher:
        """将凭证标记为已过账。"""
        raise NotImplementedError

    def void_voucher(self, voucher_id: int) -> JournalVoucher:
        """作废未过账凭证。"""
        raise NotImplementedError

    def reverse_voucher(self, command: ReverseVoucherCommand) -> JournalVoucher:
        """创建红冲凭证。"""
        raise NotImplementedError

    def list_account_balances(
        self,
        period_name: str | None = None,
    ) -> list[AccountBalance]:
        """查询科目余额。"""
        raise NotImplementedError

    def list_ledger_entries(
        self,
        period_name: str | None = None,
        subject_code: str | None = None,
        limit: int = 200,
    ) -> list[LedgerEntry]:
        """查询总账/明细账行。"""
        raise NotImplementedError

    def build_trial_balance(
        self,
        period_name: str | None = None,
    ) -> TrialBalanceReport:
        """生成试算平衡报告。"""
        raise NotImplementedError

    def run_integrity_check(self) -> list[str]:
        """执行账簿完整性检查。"""
        raise NotImplementedError
