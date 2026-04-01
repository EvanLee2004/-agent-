"""记忆记录模型。"""

from dataclasses import dataclass

from memory.memory_scope import MemoryScope


@dataclass(frozen=True)
class MemoryRecord:
    """一条已存储的记忆。"""

    scope: MemoryScope
    category: str
    content: str
    recorded_at: str
