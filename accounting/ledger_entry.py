"""账簿明细行模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LedgerEntry:
    """描述总账/明细账的一行。

    Attributes:
        voucher_id: 凭证主键。
        voucher_number: 凭证编号。
        voucher_date: 凭证日期。
        period_name: 会计期间。
        subject_code: 科目编码。
        subject_name: 科目名称。
        debit_amount: 借方金额。
        credit_amount: 贷方金额。
        summary: 凭证摘要。
        description: 分录说明。
    """

    voucher_id: int
    voucher_number: str
    voucher_date: str
    period_name: str
    subject_code: str
    subject_name: str
    debit_amount: float
    credit_amount: float
    summary: str
    description: str
