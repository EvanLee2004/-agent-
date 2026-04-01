"""审核领域模型。"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AuditTarget(str, Enum):
    """审核目标范围。"""

    LATEST = "latest"
    ALL = "all"
    VOUCHER_ID = "voucher_id"


@dataclass
class AuditRequest:
    """审核请求对象。"""

    target: AuditTarget = AuditTarget.LATEST
    voucher_id: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict) -> "AuditRequest":
        """从字典恢复审核请求。"""
        target = AuditTarget(str(data.get("target", AuditTarget.LATEST.value)).strip())
        voucher_id = data.get("voucher_id")
        if voucher_id is not None:
            voucher_id = int(voucher_id)

        request = cls(target=target, voucher_id=voucher_id)
        request.validate()
        return request

    def validate(self) -> None:
        """校验审核请求。"""
        if self.target == AuditTarget.VOUCHER_ID and self.voucher_id is None:
            raise ValueError("指定 voucher_id 审核时必须提供 voucher_id")


@dataclass
class AuditFlag:
    """审核问题标记。"""

    code: str
    severity: str
    message: str


@dataclass
class AuditResult:
    """审核结果。"""

    audited_voucher_ids: list[int]
    risk_level: str
    summary: str
    flags: list[AuditFlag] = field(default_factory=list)
    suggestion: Optional[str] = None
