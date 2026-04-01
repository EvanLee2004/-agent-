"""记账命令模型。"""

from dataclasses import dataclass

from accounting.voucher_draft import VoucherDraft


@dataclass(frozen=True)
class RecordVoucherCommand:
    """记录凭证命令。

    Attributes:
        voucher_draft: 待入账的凭证草稿。
    """

    voucher_draft: VoucherDraft
