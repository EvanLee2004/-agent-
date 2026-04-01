"""审核标记模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditFlag:
    """审核标记。"""

    code: str
    severity: str
    message: str
