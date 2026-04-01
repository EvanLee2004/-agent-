"""已持久化凭证模型。"""

from dataclasses import dataclass
from typing import Optional

from accounting.journal_line import JournalLine


@dataclass(frozen=True)
class JournalVoucher:
    """已持久化凭证。

    Attributes:
        voucher_id: 凭证主键。
        voucher_number: 凭证编号。
        voucher_date: 凭证日期。
        summary: 摘要。
        source_text: 原始文本。
        recorded_by: 记账人。
        status: 状态。
        reviewed_by: 审核人。
        anomaly_flag: 异常标记。
        anomaly_reason: 异常原因。
        created_at: 创建时间。
        lines: 分录行集合。
    """

    voucher_id: int
    voucher_number: str
    voucher_date: str
    summary: str
    source_text: str
    recorded_by: str
    status: str
    reviewed_by: Optional[str]
    anomaly_flag: Optional[str]
    anomaly_reason: Optional[str]
    created_at: str
    lines: list[JournalLine]

    def get_total_amount(self) -> float:
        """计算凭证总金额。

        Returns:
            借方合计金额。
        """
        return round(sum(line.debit_amount for line in self.lines), 2)
