"""记录银行流水命令。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RecordBankTransactionCommand:
    """记录一条银行流水。"""

    transaction_date: str
    direction: str
    amount: float
    account_name: str
    counterparty: str
    summary: str
