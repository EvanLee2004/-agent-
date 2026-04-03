"""查询资金收付记录请求。"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class QueryCashTransactionsQuery:
    """描述资金收付查询条件。"""

    date_prefix: Optional[str] = None
    direction: Optional[str] = None
    limit: int = 20

