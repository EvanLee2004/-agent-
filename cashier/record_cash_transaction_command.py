"""记录资金收付命令。"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RecordCashTransactionCommand:
    """描述一次资金收付记录请求。"""

    transaction_date: str
    direction: str
    amount: float
    account_name: str
    summary: str
    counterparty: str = ""
    status: str = "completed"
    related_voucher_id: Optional[int] = None

