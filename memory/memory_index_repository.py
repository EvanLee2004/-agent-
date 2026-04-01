"""记忆索引仓储接口。"""

from abc import ABC, abstractmethod
from pathlib import Path

from memory.memory_search_result import MemorySearchResult


class MemoryIndexRepository(ABC):
    """记忆索引仓储接口。"""

    @abstractmethod
    def rebuild_index(self, long_term_file: Path, daily_memory_dir: Path) -> None:
        """重建记忆索引。"""
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, limit: int) -> list[MemorySearchResult]:
        """搜索记忆索引。"""
        raise NotImplementedError
