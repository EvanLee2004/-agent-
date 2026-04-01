"""审核结果模型。"""

from dataclasses import dataclass, field
from typing import Optional

from audit.audit_flag import AuditFlag


@dataclass(frozen=True)
class AuditResult:
    """审核结果。"""

    audited_voucher_ids: list[int]
    risk_level: str
    summary: str
    flags: list[AuditFlag] = field(default_factory=list)
    suggestion: Optional[str] = None
