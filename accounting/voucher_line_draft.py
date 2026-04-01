"""凭证分录草稿模型。"""

from dataclasses import dataclass

from accounting.accounting_error import AccountingError


@dataclass(frozen=True)
class VoucherLineDraft:
    """待入账分录行。

    Attributes:
        subject_code: 会计科目编码。
        subject_name: 会计科目名称。
        debit_amount: 借方金额。
        credit_amount: 贷方金额。
        description: 分录说明。
    """

    subject_code: str
    subject_name: str
    debit_amount: float
    credit_amount: float
    description: str

    @classmethod
    def from_dict(cls, data: dict) -> "VoucherLineDraft":
        """从字典构造分录草稿。

        Args:
            data: 模型工具调用返回的单行数据。

        Returns:
            通过校验的分录草稿。

        Raises:
            AccountingError: 分录字段不合法时抛出。
        """
        line = cls._build_line(data)
        line.validate()
        return line

    @classmethod
    def _build_line(cls, data: dict) -> "VoucherLineDraft":
        """从原始字典构造未校验的分录草稿。"""
        return cls(
            subject_code=str(data["subject_code"]).strip(),
            subject_name=str(data["subject_name"]).strip(),
            debit_amount=float(data.get("debit_amount", 0) or 0),
            credit_amount=float(data.get("credit_amount", 0) or 0),
            description=str(data.get("description", "")).strip(),
        )

    def validate(self) -> None:
        """校验分录草稿。

        Raises:
            AccountingError: 分录数据不符合记账约束时抛出。
        """
        if not self.subject_code:
            raise AccountingError("subject_code 不能为空")
        if not self.subject_name:
            raise AccountingError("subject_name 不能为空")
        if self.debit_amount < 0 or self.credit_amount < 0:
            raise AccountingError("借贷金额不能为负数")
        if self.debit_amount > 0 and self.credit_amount > 0:
            raise AccountingError("单条分录不能同时包含借方和贷方金额")
        if self.debit_amount == 0 and self.credit_amount == 0:
            raise AccountingError("单条分录至少需要一侧金额大于 0")

    def get_line_amount(self) -> float:
        """返回分录有效金额。

        Returns:
            当前分录的有效金额。
        """
        if self.debit_amount > 0:
            return self.debit_amount
        return self.credit_amount
