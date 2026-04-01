"""凭证仓储接口。"""

from abc import ABC, abstractmethod
from typing import Optional

from accounting.journal_voucher import JournalVoucher
from accounting.record_voucher_command import RecordVoucherCommand
from accounting.query_vouchers_query import QueryVouchersQuery


class JournalRepository(ABC):
    """凭证仓储接口。"""

    @abstractmethod
    def initialize_storage(self) -> None:
        """初始化存储。

        Raises:
            OSError: 底层存储初始化失败时抛出。
        """
        raise NotImplementedError

    @abstractmethod
    def create_voucher(self, command: RecordVoucherCommand, recorded_by: str) -> int:
        """创建凭证。

        Args:
            command: 记账命令。
            recorded_by: 记账来源。

        Returns:
            新建凭证主键。
        """
        raise NotImplementedError

    @abstractmethod
    def get_voucher_by_id(self, voucher_id: int) -> Optional[JournalVoucher]:
        """按主键读取凭证。

        Args:
            voucher_id: 凭证主键。

        Returns:
            对应凭证；不存在时返回 `None`。
        """
        raise NotImplementedError

    @abstractmethod
    def get_latest_voucher(self) -> Optional[JournalVoucher]:
        """读取最新凭证。

        Returns:
            最新凭证；不存在时返回 `None`。
        """
        raise NotImplementedError

    @abstractmethod
    def list_vouchers(self, query: QueryVouchersQuery) -> list[JournalVoucher]:
        """列出凭证。

        Args:
            query: 查询条件。

        Returns:
            满足条件的凭证列表。
        """
        raise NotImplementedError

    @abstractmethod
    def update_status(
        self,
        voucher_id: int,
        status: str,
        reviewed_by: Optional[str],
    ) -> None:
        """更新凭证状态。

        Args:
            voucher_id: 凭证主键。
            status: 新状态。
            reviewed_by: 审核人。
        """
        raise NotImplementedError
