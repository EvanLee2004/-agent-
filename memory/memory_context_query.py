"""记忆上下文请求。"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MemoryContextQuery:
    """Prompt 记忆上下文请求。"""

    agent_name: str
    query: Optional[str] = None
    limit: int = 10
