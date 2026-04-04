"""科目仓储接口。"""

from abc import ABC, abstractmethod
from typing import Optional

from accounting.account_subject import AccountSubject


class ChartOfAccountsRepository(ABC):
    """科目仓储接口。"""

    @property
    @abstractmethod
    def database_path(self) -> str:
        """返回底层数据库路径。"""
        raise NotImplementedError

    @abstractmethod
    def initialize_storage(self) -> None:
        """初始化存储。"""
        raise NotImplementedError

    @abstractmethod
    def save_subjects(self, subjects: list[AccountSubject]) -> None:
        """保存会计科目列表。

        Args:
            subjects: 需要写入的科目列表。
        """
        raise NotImplementedError

    @abstractmethod
    def list_subjects(self) -> list[AccountSubject]:
        """列出全部科目。

        Returns:
            全部科目列表。
        """
        raise NotImplementedError

    @abstractmethod
    def get_subject_by_code(self, subject_code: str) -> Optional[AccountSubject]:
        """按编码获取科目。

        Args:
            subject_code: 科目编码。

        Returns:
            对应科目；不存在时返回 `None`。
        """
        raise NotImplementedError
