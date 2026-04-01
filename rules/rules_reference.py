"""规则参考模型。"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RulesReference:
    """规则参考内容。"""

    question: str
    rules_text: str
    memory_context: Optional[str] = None
    memory_notice: Optional[str] = None
