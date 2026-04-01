"""账目数据库模块

本模块已重构为使用 ledger_repository.py 的 Repository 模式。
保留本文件作为向后兼容的接口。
"""

from infrastructure.ledger_repository import (
    LEDGER_DB,
    init_ledger_db,
    init_ledger_repository,
    write_entry,
    get_entries,
    update_entry_status,
    get_ledger_repository,
    SQLiteLedgerRepository,
    ILedgerRepository,
)

__all__ = [
    "LEDGER_DB",
    "init_ledger_db",
    "init_ledger_repository",
    "write_entry",
    "get_entries",
    "update_entry_status",
    "get_ledger_repository",
    "SQLiteLedgerRepository",
    "ILedgerRepository",
]
