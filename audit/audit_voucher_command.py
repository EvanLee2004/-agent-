"""审核命令模型。"""

from dataclasses import dataclass

from audit.audit_request import AuditRequest


@dataclass(frozen=True)
class AuditVoucherCommand:
    """审核命令。"""

    audit_request: AuditRequest
