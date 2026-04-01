"""会计领域模型。

该模块收敛所有与“小企业会计记账”直接相关的核心对象：
- 会计分录草稿
- 会计凭证草稿
- 会计科目
- 已持久化凭证与分录
- 查询请求

这样拆分之后，后续继续扩总账、明细账、报表时，不需要再去一个超大文件里找类型。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class VoucherLineDraft:
    """待入账分录行。

    Attributes:
        subject_code: 会计科目编码。
        subject_name: 会计科目名称。
        debit_amount: 借方金额。
        credit_amount: 贷方金额。
        description: 行级说明，可为空。
    """

    subject_code: str
    subject_name: str
    debit_amount: float = 0.0
    credit_amount: float = 0.0
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "VoucherLineDraft":
        """从字典创建分录行并立即校验。"""
        line = cls(
            subject_code=str(data["subject_code"]).strip(),
            subject_name=str(data["subject_name"]).strip(),
            debit_amount=float(data.get("debit_amount", 0) or 0),
            credit_amount=float(data.get("credit_amount", 0) or 0),
            description=str(data.get("description", "")).strip(),
        )
        line.validate()
        return line

    def validate(self) -> None:
        """校验分录行合法性。"""
        if not self.subject_code:
            raise ValueError("subject_code 不能为空")

        if not self.subject_name:
            raise ValueError("subject_name 不能为空")

        if self.debit_amount < 0 or self.credit_amount < 0:
            raise ValueError("借贷金额不能为负数")

        if self.debit_amount > 0 and self.credit_amount > 0:
            raise ValueError("单条分录不能同时存在借方和贷方金额")

        if self.debit_amount == 0 and self.credit_amount == 0:
            raise ValueError("单条分录至少需要一侧金额大于 0")

    @property
    def line_amount(self) -> float:
        """获取该分录行的有效金额。"""
        return self.debit_amount if self.debit_amount > 0 else self.credit_amount


@dataclass
class VoucherDraft:
    """待入账凭证草稿。"""

    voucher_date: str
    summary: str
    lines: list[VoucherLineDraft]
    source_text: Optional[str] = None
    anomaly_flag: Optional[str] = None
    anomaly_reason: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "VoucherDraft":
        """从字典创建凭证草稿并应用基础规则。"""
        raw_lines = data.get("lines", [])
        if not isinstance(raw_lines, list):
            raise ValueError("lines 必须为数组")

        voucher = cls(
            voucher_date=str(
                data.get("voucher_date") or data.get("date") or ""
            ).strip(),
            summary=str(data.get("summary", "")).strip(),
            lines=[
                VoucherLineDraft.from_dict(item)
                for item in raw_lines
                if isinstance(item, dict)
            ],
            source_text=str(data.get("source_text", "")).strip() or None,
            anomaly_flag=data.get("anomaly_flag"),
            anomaly_reason=data.get("anomaly_reason"),
        )
        voucher.apply_business_rules()
        return voucher

    def apply_business_rules(self) -> None:
        """应用凭证级业务规则。"""
        if not self.voucher_date:
            raise ValueError("voucher_date 不能为空")

        if not self.summary:
            raise ValueError("summary 不能为空")

        if len(self.lines) < 2:
            raise ValueError("标准会计凭证至少需要两条分录")

        debit_total = round(sum(item.debit_amount for item in self.lines), 2)
        credit_total = round(sum(item.credit_amount for item in self.lines), 2)
        if abs(debit_total - credit_total) > 0.01:
            raise ValueError("借贷金额不平衡")

        total_amount = self.total_amount
        self.anomaly_flag = None
        self.anomaly_reason = None
        if total_amount > 50000:
            self.anomaly_flag = "high"
            self.anomaly_reason = "凭证金额超过50000，需审核"
        elif 0 < total_amount < 10:
            self.anomaly_flag = "low"
            self.anomaly_reason = "凭证金额过小"

    @property
    def total_amount(self) -> float:
        """获取凭证总金额。"""
        return round(sum(item.debit_amount for item in self.lines), 2)


@dataclass
class QueryRequest:
    """查询请求对象。"""

    date: Optional[str] = None


@dataclass
class AccountSubject:
    """会计科目。"""

    code: str
    name: str
    category: str
    normal_balance: str
    description: str = ""


@dataclass
class JournalLine:
    """已持久化的分录行。"""

    id: int
    voucher_id: int
    subject_code: str
    subject_name: str
    debit_amount: float
    credit_amount: float
    description: str


@dataclass
class JournalVoucher:
    """已持久化的凭证。"""

    id: int
    voucher_number: str
    voucher_date: str
    summary: str
    source_text: str
    recorded_by: str
    status: str
    anomaly_flag: Optional[str]
    anomaly_reason: Optional[str]
    created_at: str
    lines: list[JournalLine]
    reviewed_by: Optional[str] = None

    @property
    def total_amount(self) -> float:
        """获取凭证总金额。"""
        return round(sum(item.debit_amount for item in self.lines), 2)
