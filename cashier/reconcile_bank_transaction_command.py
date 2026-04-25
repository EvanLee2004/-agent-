"""银行流水对账命令。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReconcileBankTransactionCommand:
    """把银行流水标记为已对账。"""

    transaction_id: int
    linked_voucher_id: int | None = None
