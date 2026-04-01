"""已持久化分录模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class JournalLine:
    """已持久化分录。

    Attributes:
        line_id: 分录主键。
        voucher_id: 所属凭证主键。
        subject_code: 科目编码。
        subject_name: 科目名称。
        debit_amount: 借方金额。
        credit_amount: 贷方金额。
        description: 分录说明。
    """

    line_id: int
    voucher_id: int
    subject_code: str
    subject_name: str
    debit_amount: float
    credit_amount: float
    description: str
