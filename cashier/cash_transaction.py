"""资金收付事实模型。"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CashTransaction:
    """描述一条资金收付事实。

    Attributes:
        transaction_id: 主键。
        transaction_date: 收付日期。
        direction: 收款或付款。
        amount: 金额。
        account_name: 发生收付的账户名称。
        summary: 业务摘要。
        counterparty: 对方单位或个人。
        status: 交易状态。
        related_voucher_id: 关联凭证，可为空。
        created_at: 创建时间。
    """

    transaction_id: int
    transaction_date: str
    direction: str
    amount: float
    account_name: str
    summary: str
    counterparty: str
    status: str
    related_voucher_id: Optional[int]
    created_at: str

