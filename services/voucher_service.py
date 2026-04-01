"""凭证应用服务。

该服务为审核、查询、后续报表等能力提供统一的凭证读取入口。
与 `AccountingService` 的区别是：
- `AccountingService` 更偏向“记账入口”和兼容旧接口
- `VoucherService` 更偏向“凭证查询与读取”
"""

from typing import Optional

from domain.models import JournalVoucher
from infrastructure.accounting_repository import IJournalRepository


class VoucherService:
    """凭证查询服务。"""

    def __init__(self, journal_repository: IJournalRepository):
        self._journal_repository = journal_repository

    def get_voucher_by_id(self, voucher_id: int) -> Optional[JournalVoucher]:
        """根据主键获取凭证。"""
        return self._journal_repository.get_voucher_by_id(voucher_id)

    def get_latest_voucher(self) -> Optional[JournalVoucher]:
        """获取最近一张凭证。"""
        return self._journal_repository.get_latest_voucher()

    def list_vouchers(
        self,
        date: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[JournalVoucher]:
        """列出凭证。"""
        return self._journal_repository.list_vouchers(
            date=date,
            status=status,
            limit=limit,
        )
