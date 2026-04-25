"""红冲凭证命令。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReverseVoucherCommand:
    """创建红冲凭证。

    Attributes:
        voucher_id: 被红冲的原凭证 ID。
        reversal_date: 红冲日期；为空时使用原凭证日期。
        recorded_by: 红冲操作来源。
    """

    voucher_id: int
    reversal_date: str | None = None
    recorded_by: str = "智能财务部门"
