"""银行流水查询条件。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class QueryBankTransactionsQuery:
    """查询银行流水。"""

    date_prefix: str | None = None
    status: str | None = None
    direction: str | None = None
    limit: int = 20
