"""记忆搜索请求。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchMemoryQuery:
    """记忆搜索请求。"""

    query: str
    limit: int = 10
