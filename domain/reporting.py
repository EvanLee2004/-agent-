"""报表领域模型。

当前阶段仅定义报表接口会用到的基础数据结构，
为后续总账、科目余额表、试算平衡表等能力预留边界。
"""

from dataclasses import dataclass, field


@dataclass
class TrialBalanceRow:
    """试算平衡表单行。"""

    subject_code: str
    subject_name: str
    debit_total: float
    credit_total: float


@dataclass
class TrialBalanceReport:
    """试算平衡表。"""

    generated_at: str
    rows: list[TrialBalanceRow] = field(default_factory=list)
