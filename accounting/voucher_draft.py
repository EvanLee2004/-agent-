"""凭证草稿模型。"""

from dataclasses import dataclass, replace
from typing import Optional

from accounting.accounting_error import AccountingError
from accounting.voucher_line_draft import VoucherLineDraft
from configuration.defaults import HIGH_AMOUNT_THRESHOLD, LOW_AMOUNT_THRESHOLD


BALANCE_TOLERANCE = 0.01


def _build_line_drafts(raw_lines: list) -> list[VoucherLineDraft]:
    """把原始分录列表转换为分录草稿集合。"""
    return [
        VoucherLineDraft.from_dict(item)
        for item in raw_lines
        if isinstance(item, dict)
    ]


def _build_voucher_draft(data: dict, raw_lines: list) -> "VoucherDraft":
    """从原始字典构造未应用规则的凭证草稿。"""
    return VoucherDraft(
        voucher_date=str(data.get("voucher_date") or "").strip(),
        summary=str(data.get("summary", "")).strip(),
        lines=_build_line_drafts(raw_lines),
        source_text=str(data.get("source_text", "")).strip() or None,
    )


@dataclass(frozen=True)
class VoucherDraft:
    """待入账凭证草稿。

    Attributes:
        voucher_date: 凭证日期。
        summary: 摘要。
        lines: 分录集合。
        source_text: 原始文本。
        anomaly_flag: 异常标记。
        anomaly_reason: 异常原因。
    """

    voucher_date: str
    summary: str
    lines: list[VoucherLineDraft]
    source_text: Optional[str] = None
    anomaly_flag: Optional[str] = None
    anomaly_reason: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "VoucherDraft":
        """从字典构造凭证草稿。

        Args:
            data: 模型工具调用返回的数据。

        Returns:
            应用过业务规则的凭证草稿。

        Raises:
            AccountingError: 凭证结构不合法时抛出。
        """
        raw_lines = data.get("lines", [])
        if not isinstance(raw_lines, list):
            raise AccountingError("lines 必须是数组")
        draft = _build_voucher_draft(data, raw_lines)
        return draft.apply_business_rules()

    def apply_business_rules(self) -> "VoucherDraft":
        """应用凭证级业务规则。

        Returns:
            带有异常标记信息的新凭证草稿。

        Raises:
            AccountingError: 借贷不平或基础字段缺失时抛出。
        """
        self._validate_required_fields()
        self._validate_balance()
        return self._apply_amount_flags()

    def get_total_amount(self) -> float:
        """计算凭证总金额。

        Returns:
            凭证借方合计金额。
        """
        return round(sum(line.debit_amount for line in self.lines), 2)

    def _validate_required_fields(self) -> None:
        """校验基础字段完整性。

        Raises:
            AccountingError: 基础字段缺失时抛出。
        """
        if not self.voucher_date:
            raise AccountingError("voucher_date 不能为空")
        if not self.summary:
            raise AccountingError("summary 不能为空")
        if len(self.lines) < 2:
            raise AccountingError("标准凭证至少需要两条分录")

    def _validate_balance(self) -> None:
        """校验借贷平衡。

        Raises:
            AccountingError: 借贷不平时抛出。
        """
        total_debit = round(sum(line.debit_amount for line in self.lines), 2)
        total_credit = round(sum(line.credit_amount for line in self.lines), 2)
        if abs(total_debit - total_credit) > BALANCE_TOLERANCE:
            raise AccountingError("借贷金额不平衡")

    def _apply_amount_flags(self) -> "VoucherDraft":
        """根据金额打标。

        Returns:
            带异常标记的新凭证草稿。
        """
        total_amount = self.get_total_amount()
        if total_amount > HIGH_AMOUNT_THRESHOLD:
            return replace(
                self,
                anomaly_flag="high",
                anomaly_reason="凭证金额超过50000，需审核",
            )
        if 0 < total_amount < LOW_AMOUNT_THRESHOLD:
            return replace(
                self,
                anomaly_flag="low",
                anomaly_reason="凭证金额过小",
            )
        return replace(self, anomaly_flag=None, anomaly_reason=None)
