"""记忆领域模型。"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MemoryScope(str, Enum):
    """记忆写入范围。"""

    LONG_TERM = "long_term"
    DAILY = "daily"


@dataclass
class ExperienceRecord:
    """长期记忆中的一条经验记录。"""

    type: str
    content: str
    result: str
    learned_at: str
    feedback: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为可序列化字典。"""
        data = {
            "type": self.type,
            "content": self.content,
            "result": self.result,
            "learned_at": self.learned_at,
        }
        if self.feedback:
            data["feedback"] = self.feedback
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ExperienceRecord":
        """从字典恢复经验对象。"""
        return cls(
            type=str(data.get("type", "经验")),
            content=str(data.get("content", "")),
            result=str(data.get("result", "")),
            learned_at=str(data.get("learned_at", "")),
            feedback=str(data["feedback"]) if data.get("feedback") else None,
        )


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
