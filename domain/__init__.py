"""领域层包。

当前直接按业务边界显式导出领域对象，避免再通过兼容聚合模块转发，
这样可以让导入路径和真实领域边界保持一致。
"""

from domain.accounting import (
    AccountSubject,
    JournalLine,
    JournalVoucher,
    QueryRequest,
    VoucherDraft,
    VoucherLineDraft,
)
from domain.audit import AuditFlag, AuditRequest, AuditResult, AuditTarget
from domain.memory import MemoryDecision, MemoryRecord, MemoryScope, MemorySearchResult
from domain.tax import TaxComputationResult, TaxRequest, TaxType, TaxpayerType


__all__ = [
    "AccountSubject",
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
