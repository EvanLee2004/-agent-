"""旧账本接口兼容层。

该模块继续保留原有 `ledger.py` 的对外函数名，但内部已经不再把 `ledger` 表
当作主业务真相。新的兼容策略是：

1. 写入旧接口时，实际落到新版 `journal_voucher/journal_line`
2. 查询旧接口时，从新版凭证投影成旧 ledger 风格数据
3. `ledger_repository.py` 仍保留给历史脚本或旧数据迁移使用，但主流程不再依赖它
"""

from typing import Optional

from bootstrap import bootstrap_default_application
from domain.models import AccountingEntryDraft, QueryRequest
from infrastructure.accounting_repository import (
    get_chart_of_accounts_repository,
    get_journal_repository,
)
from infrastructure.ledger_repository import (
    LEDGER_DB,
    ILedgerRepository,
    SQLiteLedgerRepository,
    get_ledger_repository,
)
from services.accounting_service import AccountingService
from services.chart_of_accounts_service import ChartOfAccountsService
from services.legacy_ledger_projection_service import LegacyLedgerProjectionService
from services.voucher_service import VoucherService


def init_ledger_db() -> None:
    """初始化数据库（向后兼容）。"""
    bootstrap_default_application()


def init_ledger_repository() -> None:
    """兼容旧接口：初始化旧账本仓库。"""
    get_ledger_repository().init_db()


def write_entry(
    datetime: str,
    type_: str,
    amount: float,
    description: str,
    recorded_by: str = "accountant",
    anomaly_flag: Optional[str] = None,
    anomaly_reason: Optional[str] = None,
) -> int:
    """兼容旧接口：写入账目。

    说明：
    - 旧接口表面上仍接收 `datetime/type/amount/description`
    - 实际内部已经转换成标准凭证，再落入新版主账
    """
    del anomaly_flag, anomaly_reason
    bootstrap_default_application()
    chart_service = ChartOfAccountsService(get_chart_of_accounts_repository())
    accounting_service = AccountingService(
        journal_repository=get_journal_repository(),
        chart_of_accounts_service=chart_service,
        recorded_by=recorded_by,
    )
    entry = AccountingEntryDraft(
        date=datetime[:10],
        entry_type=type_,
        amount=amount,
        description=description,
    )
    entry.apply_business_rules()
    return accounting_service.record_entry(entry)


def get_entries(
    date: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """兼容旧接口：查询账目列表。"""
    bootstrap_default_application()
    voucher_service = VoucherService(get_journal_repository())
    projection_service = LegacyLedgerProjectionService()
    vouchers = voucher_service.list_vouchers(date=date, status=status, limit=limit)
    return projection_service.project_vouchers(vouchers)


def update_entry_status(
    entry_id: int,
    status: str,
    reviewed_by: str = "auditor",
) -> None:
    """兼容旧接口：更新状态。

    当前实现把旧接口的 entry_id 视为新版凭证 ID。
    """
    bootstrap_default_application()
    get_journal_repository().update_status(
        voucher_id=entry_id,
        status=status,
        reviewed_by=reviewed_by,
    )


def get_entries_by_query_request(query_request: QueryRequest) -> list[dict]:
    """辅助兼容方法：按 QueryRequest 查询并投影。"""
    return get_entries(date=query_request.date)


__all__ = [
    "LEDGER_DB",
    "ILedgerRepository",
    "SQLiteLedgerRepository",
    "get_ledger_repository",
    "get_entries",
    "get_entries_by_query_request",
    "init_ledger_db",
    "init_ledger_repository",
    "update_entry_status",
    "write_entry",
]
