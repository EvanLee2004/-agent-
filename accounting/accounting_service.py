"""会计服务。"""

from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.journal_repository import JournalRepository
from accounting.journal_voucher import JournalVoucher
from accounting.query_vouchers_query import QueryVouchersQuery
from accounting.record_voucher_command import RecordVoucherCommand


DEFAULT_RECORDED_BY = "智能会计部门"


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
