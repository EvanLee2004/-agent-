"""记忆领域模型。"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MemoryScope(str, Enum):
    """记忆写入范围。"""

    LONG_TERM = "long_term"
    DAILY = "daily"


@dataclass
class MemoryRecord:
    """一条已存储的记忆记录。"""

    scope: MemoryScope
    category: str
    content: str
    recorded_at: str


@dataclass
class MemorySearchResult:
    """记忆搜索结果。"""

    path: str
    scope: MemoryScope
    category: str
    content: str
    start_line: int
    end_line: int
    score: float


@dataclass
class MemoryDecision:
    """记忆 skill 输出的写入决策。"""

    action: str
    scope: Optional[MemoryScope] = None
    category: Optional[str] = None
    content: Optional[str] = None
    acknowledgement: Optional[str] = None
    reason: Optional[str] = None

    @property
    def should_store(self) -> bool:
        """是否需要写入记忆。"""
        return (
            self.action == "store"
            and self.scope is not None
            and bool(self.category)
            and bool(self.content)
        )
