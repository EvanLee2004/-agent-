"""记忆搜索结果模型。"""

from dataclasses import dataclass

from memory.memory_scope import MemoryScope


@dataclass(frozen=True)
class MemorySearchResult:
    """记忆搜索结果。"""

    path: str
    scope: MemoryScope
    category: str
    content: str
    start_line: int
    end_line: int
    score: float
