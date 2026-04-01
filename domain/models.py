"""领域模型兼容导出模块。

当前项目已经把领域对象按业务边界拆分到了多个模块：
- `domain.accounting`
- `domain.tax`
- `domain.audit`
- `domain.memory`

但为了避免一次性打断现有导入路径，这里继续保留 `domain.models`
作为统一兼容出口。
"""

from domain.accounting import (
    AccountSubject,
    AccountingEntryDraft,
    JournalLine,
    JournalVoucher,
    QueryRequest,
    VoucherDraft,
    VoucherLineDraft,
)
from domain.audit import AuditFlag, AuditRequest, AuditResult, AuditTarget
from domain.memory import (
    MemoryDecision,
    MemoryRecord,
    MemoryScope,
    MemorySearchResult,
)
from domain.tax import TaxComputationResult, TaxRequest, TaxpayerType, TaxType

__all__ = [
    "AccountSubject",
    "AccountingEntryDraft",
    "AuditFlag",
    "AuditRequest",
    "AuditResult",
    "AuditTarget",
    "JournalLine",
    "JournalVoucher",
    "MemoryDecision",
    "MemoryRecord",
    "MemoryScope",
    "MemorySearchResult",
    "QueryRequest",
    "TaxComputationResult",
    "TaxRequest",
    "TaxType",
    "TaxpayerType",
    "VoucherDraft",
    "VoucherLineDraft",
]
