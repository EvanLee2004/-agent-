"""凭证查询模型。"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class QueryVouchersQuery:
    """凭证查询请求。

    Attributes:
        date_prefix: 日期前缀过滤条件。
        status: 状态过滤条件。
        limit: 最大返回条数。
    """

    date_prefix: Optional[str] = None
    status: Optional[str] = None
    limit: int = 20
