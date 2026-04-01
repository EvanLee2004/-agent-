"""写记忆命令。"""

from dataclasses import dataclass

from memory.memory_scope import MemoryScope


@dataclass(frozen=True)
class StoreMemoryCommand:
    """写记忆命令。"""

    scope: MemoryScope
    category: str
    content: str
