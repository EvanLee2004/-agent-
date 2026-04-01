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
class AccountingEntryDraft:
    """待入账的旧版流水账草稿。

    该对象作为兼容层继续保留，但不再是新版系统的主路径。
    新版主路径统一走 `VoucherDraft`。
    """

    date: str
    entry_type: str
    amount: float
    description: str
    anomaly_flag: Optional[str] = None
    anomaly_reason: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "AccountingEntryDraft":
        """从字典创建流水账草稿，并立即应用业务规则。"""
        draft = cls(
            date=str(data["date"]).strip(),
            entry_type=str(data["type"]).strip(),
            amount=float(data["amount"]),
            description=str(data["description"]).strip(),
            anomaly_flag=data.get("anomaly_flag"),
            anomaly_reason=data.get("anomaly_reason"),
        )
        draft.apply_business_rules()
        return draft

    def apply_business_rules(self) -> None:
        """应用项目级流水账规则。"""
        if self.entry_type not in ("收入", "支出"):
            raise ValueError("type 必须为 收入 或 支出")

        if self.amount <= 0:
            raise ValueError("amount 必须为正数")

        if not self.description:
            raise ValueError("description 不能为空")

        self.anomaly_flag = None
        self.anomaly_reason = None

        if self.amount > 50000:
            self.anomaly_flag = "high"
            self.anomaly_reason = "金额超过50000，需审核"
        elif self.amount < 10:
            self.anomaly_flag = "low"
            self.anomaly_reason = "金额过小"

    def to_voucher_draft(self) -> VoucherDraft:
        """把旧版流水账草稿转换为标准凭证草稿。"""
        if self.entry_type == "支出":
            lines = [
                VoucherLineDraft(
                    subject_code="6602",
                    subject_name="管理费用",
                    debit_amount=self.amount,
                    credit_amount=0.0,
                    description=self.description,
                ),
                VoucherLineDraft(
                    subject_code="1001",
                    subject_name="库存现金",
                    debit_amount=0.0,
                    credit_amount=self.amount,
                    description=self.description,
                ),
            ]
        else:
            lines = [
                VoucherLineDraft(
                    subject_code="1002",
                    subject_name="银行存款",
                    debit_amount=self.amount,
                    credit_amount=0.0,
                    description=self.description,
                ),
                VoucherLineDraft(
                    subject_code="5001",
                    subject_name="主营业务收入",
                    debit_amount=0.0,
                    credit_amount=self.amount,
                    description=self.description,
                ),
            ]

        voucher = VoucherDraft(
            voucher_date=self.date,
            summary=self.description,
            lines=lines,
            source_text=self.description,
        )
        voucher.apply_business_rules()
        return voucher

    def to_intent_dict(self) -> dict:
        """转换为与现有 JSON 协议兼容的字典结构。"""
        return {
            "date": self.date,
            "amount": self.amount,
            "type": self.entry_type,
            "description": self.description,
            "anomaly_flag": self.anomaly_flag,
            "anomaly_reason": self.anomaly_reason,
        }


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
