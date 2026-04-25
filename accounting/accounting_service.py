"""会计服务。"""

from accounting.account_balance import AccountBalance
from accounting.accounting_period import AccountingPeriod
from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.correct_voucher_command import CorrectVoucherCommand
from accounting.journal_repository import JournalRepository
from accounting.journal_voucher import JournalVoucher
from accounting.ledger_entry import LedgerEntry
from accounting.query_vouchers_query import QueryVouchersQuery
from accounting.record_voucher_command import RecordVoucherCommand
from accounting.reverse_voucher_command import ReverseVoucherCommand
from accounting.trial_balance_report import TrialBalanceReport


DEFAULT_RECORDED_BY = "智能财务部门"


class AccountingService:
    """会计服务。"""

    def __init__(
        self,
        journal_repository: JournalRepository,
        chart_of_accounts_service: ChartOfAccountsService,
        recorded_by: str = DEFAULT_RECORDED_BY,
    ):
        self._journal_repository = journal_repository
        self._chart_of_accounts_service = chart_of_accounts_service
        self._recorded_by = recorded_by

    def record_voucher(self, command: RecordVoucherCommand) -> int:
        """记录凭证。

        Args:
            command: 记账命令。

        Returns:
            新建凭证主键。
        """
        self._chart_of_accounts_service.validate_voucher_subjects(command.voucher_draft)
        return self._journal_repository.create_voucher(
            command=command,
            recorded_by=self._recorded_by,
        )

    def query_vouchers(self, query: QueryVouchersQuery) -> list[JournalVoucher]:
        """查询凭证。

        Args:
            query: 查询条件。

        Returns:
            满足条件的凭证列表。
        """
        return self._journal_repository.list_vouchers(query)

    def get_voucher(self, voucher_id: int) -> JournalVoucher | None:
        """按 ID 查询凭证。"""
        return self._journal_repository.get_voucher_by_id(voucher_id)

    def list_periods(self) -> list[AccountingPeriod]:
        """列出全部会计期间。"""
        return self._journal_repository.list_periods()

    def open_period(self, period_name: str) -> AccountingPeriod:
        """打开或创建会计期间。"""
        return self._journal_repository.open_period(period_name)

    def close_period(self, period_name: str) -> AccountingPeriod:
        """关闭会计期间。"""
        return self._journal_repository.close_period(period_name)

    def post_voucher(self, voucher_id: int) -> JournalVoucher:
        """过账凭证。"""
        return self._journal_repository.post_voucher(voucher_id)

    def void_voucher(self, voucher_id: int) -> JournalVoucher:
        """作废未过账凭证。"""
        return self._journal_repository.void_voucher(voucher_id)

    def reverse_voucher(self, command: ReverseVoucherCommand) -> JournalVoucher:
        """创建红冲凭证。"""
        return self._journal_repository.reverse_voucher(command)

    def correct_voucher(self, command: CorrectVoucherCommand) -> tuple[int, int]:
        """通过红冲原凭证并写入新凭证完成更正。

        Args:
            command: 更正命令。

        Returns:
            (红冲凭证 ID, 新凭证 ID)。
        """
        reversal = self.reverse_voucher(
            ReverseVoucherCommand(
                voucher_id=command.voucher_id,
                reversal_date=command.reversal_date,
                recorded_by=command.recorded_by,
            )
        )
        self._chart_of_accounts_service.validate_voucher_subjects(
            command.replacement_command.voucher_draft
        )
        replacement_id = self._journal_repository.create_voucher(
            command=command.replacement_command,
            recorded_by=command.recorded_by,
        )
        self._journal_repository.post_voucher(replacement_id)
        return reversal.voucher_id, replacement_id

    def list_account_balances(
        self,
        period_name: str | None = None,
    ) -> list[AccountBalance]:
        """查询科目余额。"""
        return self._journal_repository.list_account_balances(period_name)

    def list_ledger_entries(
        self,
        period_name: str | None = None,
        subject_code: str | None = None,
        limit: int = 200,
    ) -> list[LedgerEntry]:
        """查询总账/明细账。"""
        return self._journal_repository.list_ledger_entries(
            period_name=period_name,
            subject_code=subject_code,
            limit=limit,
        )

    def build_trial_balance(
        self,
        period_name: str | None = None,
    ) -> TrialBalanceReport:
        """生成试算平衡报告。"""
        return self._journal_repository.build_trial_balance(period_name)

    def run_integrity_check(self) -> list[str]:
        """执行账簿完整性检查。"""
        return self._journal_repository.run_integrity_check()
