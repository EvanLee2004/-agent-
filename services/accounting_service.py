"""会计应用服务。

当前版本把会计服务收口为“主账写入和凭证查询”两类职责：
- 记录标准凭证
- 兼容旧版流水账输入
- 查询并格式化凭证

重要边界：
- `journal_voucher/journal_line/account_subject` 才是唯一业务主账
- 不再维护旧 `ledger` 兼容写入
"""

from typing import Optional

from domain.accounting import JournalVoucher, QueryRequest, VoucherDraft
from infrastructure.accounting_repository import IJournalRepository
from services.chart_of_accounts_service import ChartOfAccountsService


class AccountingService:
    """会计应用服务。"""

    def __init__(
        self,
        journal_repository: IJournalRepository,
        chart_of_accounts_service: ChartOfAccountsService,
        recorded_by: str = "智能会计",
    ):
        self._journal_repository = journal_repository
        self._chart_of_accounts_service = chart_of_accounts_service
        self._recorded_by = recorded_by

    def record_voucher(self, voucher: VoucherDraft) -> int:
        """记录标准凭证。"""
        voucher.apply_business_rules()
        self._chart_of_accounts_service.validate_voucher_subjects(voucher)
        return self._journal_repository.create_voucher(
            voucher=voucher,
            recorded_by=self._recorded_by,
        )

    def list_entries(
        self,
        query_request: Optional[QueryRequest] = None,
        status: Optional[str] = None,
    ) -> list[JournalVoucher]:
        """根据查询条件获取凭证列表。"""
        if query_request:
            return self._journal_repository.list_vouchers(
                date=query_request.date,
                status=status,
            )
        return self._journal_repository.list_vouchers(status=status)
