"""内存版财务部门工作台仓储。"""

from typing import Optional

from department.workbench.department_workbench import DepartmentWorkbench
from department.workbench.department_workbench_repository import DepartmentWorkbenchRepository


class InMemoryDepartmentWorkbenchRepository(DepartmentWorkbenchRepository):
    """使用进程内存保存协作工作台。

    当前产品形态先以 CLI 为主，因此“当前回合的协作轨迹”使用进程内存就足够。
    后续如果要加 API 或多实例部署，再把这一层替换成外部存储，不会影响协作服务。
    """

    def __init__(self):
        self._workbenches: dict[str, DepartmentWorkbench] = {}

    def save(self, workbench: DepartmentWorkbench) -> None:
        """保存工作台。"""
        self._workbenches[workbench.thread_id] = workbench

    def get(self, thread_id: str) -> Optional[DepartmentWorkbench]:
        """读取工作台。"""
        return self._workbenches.get(thread_id)
