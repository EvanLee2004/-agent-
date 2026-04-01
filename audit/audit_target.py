"""审核目标枚举。"""

from enum import Enum


class AuditTarget(str, Enum):
    """审核目标范围。"""

    LATEST = "latest"
    ALL = "all"
    VOUCHER_ID = "voucher_id"
