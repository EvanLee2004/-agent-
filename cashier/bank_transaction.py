"""银行流水模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BankTransaction:
    """描述一条出纳/银行流水。"""

    transaction_id: int
    transaction_date: str
    direction: str
    amount: float
    account_name: str
    counterparty: str
    summary: str
    status: str
    linked_voucher_id: int | None = None
    created_at: str | None = None
