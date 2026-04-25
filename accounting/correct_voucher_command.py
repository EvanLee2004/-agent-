"""更正凭证命令。"""

from dataclasses import dataclass

from accounting.record_voucher_command import RecordVoucherCommand


@dataclass(frozen=True)
class CorrectVoucherCommand:
    """用红冲加新凭证的方式更正已过账凭证。

    Attributes:
        voucher_id: 被更正的原凭证 ID。
        replacement_command: 新凭证记录命令。
        reversal_date: 红冲日期；为空时使用原凭证日期。
        recorded_by: 更正操作来源。
    """

    voucher_id: int
    replacement_command: RecordVoucherCommand
    reversal_date: str | None = None
    recorded_by: str = "智能财务部门"
