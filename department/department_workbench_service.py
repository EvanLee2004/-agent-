"""财务部门共享工作台服务。"""

from department.department_error import DepartmentError
from department.department_workbench import DepartmentWorkbench
from department.department_workbench_repository import DepartmentWorkbenchRepository
from department.role_trace import RoleTrace


MAX_COLLABORATION_COUNT = 12


def _append_trace(workbench: DepartmentWorkbench, trace: RoleTrace) -> DepartmentWorkbench:
    """向工作台追加一条轨迹。"""
    return DepartmentWorkbench(
        thread_id=workbench.thread_id,
        original_user_input=workbench.original_user_input,
        collaboration_count=workbench.collaboration_count,
        role_traces=[*workbench.role_traces, trace],
    )


def _increment_collaboration_count(workbench: DepartmentWorkbench) -> DepartmentWorkbench:
    """递增当前回合协作次数。"""
    return DepartmentWorkbench(
        thread_id=workbench.thread_id,
        original_user_input=workbench.original_user_input,
        collaboration_count=workbench.collaboration_count + 1,
        role_traces=list(workbench.role_traces),
    )


class DepartmentWorkbenchService:
    """管理部门共享工作台。

    共享工作台是“角色协作过程”的单一事实来源。它不参与角色决策，只负责保存当前
    回合的用户任务、已发生的协作次数，以及需要展示给用户的角色思考摘要。
    """

    def __init__(self, repository: DepartmentWorkbenchRepository):
        self._repository = repository

    def start_turn(self, thread_id: str, original_user_input: str) -> None:
        """初始化当前回合工作台。"""
        self._repository.save(
            DepartmentWorkbench(
                thread_id=thread_id,
                original_user_input=original_user_input,
            )
        )

    def reserve_collaboration(self, thread_id: str) -> None:
        """登记一次角色协作。

        Args:
            thread_id: 当前线程标识。

        Raises:
            DepartmentError: 当前回合协作次数超限时抛出。
        """
        workbench = self._require_workbench(thread_id)
        if workbench.collaboration_count >= MAX_COLLABORATION_COUNT:
            raise DepartmentError("当前回合的角色协作次数过多，请缩小任务范围后重试")
        self._repository.save(_increment_collaboration_count(workbench))

    def record_role_trace(self, thread_id: str, trace: RoleTrace) -> None:
        """记录一条角色轨迹。"""
        workbench = self._require_workbench(thread_id)
        self._repository.save(_append_trace(workbench, trace))

    def list_role_traces(self, thread_id: str) -> list[RoleTrace]:
        """读取当前回合全部角色轨迹。"""
        return list(self._require_workbench(thread_id).role_traces)

    def get_original_user_input(self, thread_id: str) -> str:
        """读取当前回合原始用户输入。"""
        return self._require_workbench(thread_id).original_user_input

    def _require_workbench(self, thread_id: str) -> DepartmentWorkbench:
        """读取工作台并确保其存在。"""
        workbench = self._repository.get(thread_id)
        if workbench is None:
            raise DepartmentError("当前线程尚未初始化财务部门工作台")
        return workbench

