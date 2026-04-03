"""财务部门工作台仓储接口。"""

from abc import ABC, abstractmethod
from typing import Optional

from department.department_workbench import DepartmentWorkbench


class DepartmentWorkbenchRepository(ABC):
    """定义工作台仓储接口。"""

    @abstractmethod
    def save(self, workbench: DepartmentWorkbench) -> None:
        """保存当前线程的工作台。

        Args:
            workbench: 待保存的工作台对象。
        """

    @abstractmethod
    def get(self, thread_id: str) -> Optional[DepartmentWorkbench]:
        """读取某个线程当前回合的工作台。

        Args:
            thread_id: 线程标识。

        Returns:
            当前线程的工作台；不存在时返回 None。
        """

