"""记忆决策模型。"""

from dataclasses import dataclass
from typing import Optional

from memory.memory_scope import MemoryScope


@dataclass(frozen=True)
class MemoryDecision:
    """记忆写入决策。"""

    action: str
    scope: Optional[MemoryScope] = None
    category: Optional[str] = None
    content: Optional[str] = None
    reason: Optional[str] = None

    def should_store(self) -> bool:
        """判断是否需要写入记忆。"""
        return (
            self.action == "store"
            and self.scope is not None
            and bool(self.category)
            and bool(self.content)
        )
