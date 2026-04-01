"""报表服务接口定义。

当前阶段先定义接口，不急着实现完整报表。
这样做的意义是：
- 先把“报表属于应用服务层”的边界定下来
- 避免后续直接在 Agent 或 Repository 中硬写报表逻辑
"""

from abc import ABC, abstractmethod
from typing import Optional

from domain.models import TrialBalanceReport


class IAccountingReportService(ABC):
    """会计报表服务接口。"""

    @abstractmethod
    def build_trial_balance(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> TrialBalanceReport:
        """生成试算平衡表。"""
        pass
