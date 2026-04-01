"""记忆存储仓储接口。"""

from abc import ABC, abstractmethod
from pathlib import Path

from memory.memory_decision import MemoryDecision
from memory.memory_record import MemoryRecord


class MemoryStoreRepository(ABC):
    """记忆存储仓储接口。"""

    @abstractmethod
    def store_memory_decision(self, agent_name: str, memory_decision: MemoryDecision) -> None:
        """根据决策写入记忆。"""
        raise NotImplementedError

    @abstractmethod
    def read_long_term_records(self) -> list[MemoryRecord]:
        """读取长期记忆。"""
        raise NotImplementedError

    @abstractmethod
    def read_recent_daily_records(self, days: int) -> list[MemoryRecord]:
        """读取近期每日记忆。"""
        raise NotImplementedError

    @abstractmethod
    def clear_memory(self, agent_name: str) -> None:
        """清理记忆。"""
        raise NotImplementedError

    @abstractmethod
    def get_long_term_memory_file(self) -> Path:
        """返回长期记忆文件路径。"""
        raise NotImplementedError

    @abstractmethod
    def get_daily_memory_dir(self) -> Path:
        """返回每日记忆目录路径。"""
        raise NotImplementedError
