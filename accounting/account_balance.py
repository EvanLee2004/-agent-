"""科目余额模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountBalance:
    """描述某一科目在指定范围内的发生额与余额。

    Attributes:
        subject_code: 科目编码。
        subject_name: 科目名称。
        normal_balance: 正常余额方向，debit 或 credit。
        debit_total: 借方发生额。
        credit_total: 贷方发生额。
        balance_direction: 当前余额方向。
        balance_amount: 当前余额金额。
    """

    subject_code: str
    subject_name: str
    normal_balance: str
    debit_total: float
    credit_total: float
    balance_direction: str
    balance_amount: float
