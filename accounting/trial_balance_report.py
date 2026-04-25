"""试算平衡报告模型。"""

from dataclasses import dataclass, field

from accounting.account_balance import AccountBalance


@dataclass(frozen=True)
class TrialBalanceReport:
    """描述试算平衡结果。

    Attributes:
        period_name: 报表期间；为空表示全部已过账凭证。
        debit_total: 借方合计。
        credit_total: 贷方合计。
        difference: 借贷差额。
        balanced: 是否平衡。
        rows: 科目余额明细。
    """

    period_name: str | None
    debit_total: float
    credit_total: float
    difference: float
    balanced: bool
    rows: list[AccountBalance] = field(default_factory=list)
