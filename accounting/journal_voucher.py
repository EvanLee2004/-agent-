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
        period_name: 会计期间。
        voucher_sequence: 期间内连续编号。
        source_voucher_id: 红冲/更正来源凭证 ID。
        lifecycle_action: 生命周期动作，normal/reversal/correction。
        posted_at: 过账时间。
        voided_at: 作废时间。
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
    period_name: str = ""
    voucher_sequence: int = 0
    source_voucher_id: Optional[int] = None
    lifecycle_action: str = "normal"
    posted_at: Optional[str] = None
    voided_at: Optional[str] = None

    def get_total_amount(self) -> float:
        """计算凭证总金额。

        Returns:
            借方合计金额。
        """
        return round(sum(line.debit_amount for line in self.lines), 2)
