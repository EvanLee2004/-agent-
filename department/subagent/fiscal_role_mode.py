"""财务子代理专业模式枚举。"""

from enum import Enum


class FiscalRoleMode(Enum):
    """支持的财务专业模式。"""

    BOOKKEEPING = "bookkeeping"
    TAX = "tax"
    AUDIT = "audit"
    CASHIER = "cashier"
    POLICY_RESEARCH = "policy_research"
