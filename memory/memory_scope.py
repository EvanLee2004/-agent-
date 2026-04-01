"""记忆范围枚举。"""

from enum import Enum


class MemoryScope(str, Enum):
    """记忆写入范围。"""

    LONG_TERM = "long_term"
    DAILY = "daily"
