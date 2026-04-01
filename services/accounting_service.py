"""会计应用服务。

当前版本把会计服务收口为“主账写入和凭证查询”两类职责：
- 记录标准凭证
- 兼容旧版流水账输入
- 查询并格式化凭证

重要边界：
- `journal_voucher/journal_line/account_subject` 才是唯一业务主账
- 旧 `ledger` 不再由这里维护双写
- 旧账本兼容能力统一交给独立的投影/适配层
"""

from typing import Optional

from domain.models import AccountingEntryDraft, JournalVoucher, QueryRequest, VoucherDraft
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

    def record_entry(self, entry: AccountingEntryDraft) -> int:
        """兼容旧版流水账入账。"""
        return self.record_voucher(entry.to_voucher_draft())

    def record_voucher(self, voucher: VoucherDraft) -> int:
        """记录标准凭证。"""
        voucher.apply_business_rules()
        self._chart_of_accounts_service.validate_voucher_subjects(voucher)
        return self._journal_repository.create_voucher(
            voucher=voucher,
            recorded_by=self._recorded_by,
        )

    def build_record_success_message(
        self,
        voucher_id: int,
        voucher: VoucherDraft,
    ) -> str:
        """构造记账成功消息。"""
        result = (
            f"记账成功 [凭证ID:{voucher_id}] {voucher.summary} | "
            f"金额 {voucher.total_amount:.2f}元"
        )
        if voucher.anomaly_reason:
            result += f"（{voucher.anomaly_reason}）"
        return result

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

    def format_entries(self, entries: list[JournalVoucher]) -> str:
        """把凭证列表格式化为用户可读文本。"""
        if not entries:
            return "暂无账目记录"

        lines = []
        for voucher in entries:
            status_icon = "✓" if voucher.status == "approved" else "⏳"
            lines.append(
                f"[{voucher.id}] {status_icon} {voucher.voucher_date} "
                f"{voucher.summary} | 金额 {voucher.total_amount:.2f}元"
            )
            for line in voucher.lines:
                lines.append(
                    f"  - {line.subject_code} {line.subject_name} | "
                    f"借 {line.debit_amount:.2f} | 贷 {line.credit_amount:.2f}"
                )
        return "\n".join(lines)
