"""审核请求模型。"""

from dataclasses import dataclass
from typing import Optional

from audit.audit_error import AuditError
from audit.audit_target import AuditTarget


@dataclass(frozen=True)
class AuditRequest:
    """审核请求。"""

    target: AuditTarget = AuditTarget.LATEST
    voucher_id: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict) -> "AuditRequest":
        """从字典构造审核请求。"""
        request = cls(
            target=AuditTarget(str(data.get("target", AuditTarget.LATEST.value)).strip()),
            voucher_id=int(data["voucher_id"]) if data.get("voucher_id") is not None else None,
        )
        request.validate()
        return request

    def validate(self) -> None:
        """校验审核请求。"""
        if self.target == AuditTarget.VOUCHER_ID and self.voucher_id is None:
            raise AuditError("指定 voucher_id 审核时必须提供 voucher_id")
