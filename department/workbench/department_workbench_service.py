"""财务部门共享工作台服务。"""

from department.department_error import DepartmentError
from department.workbench.collaboration_step import CollaborationStep
from department.workbench.department_workbench import DepartmentWorkbench
from department.workbench.department_workbench_repository import DepartmentWorkbenchRepository


def _append_step(workbench: DepartmentWorkbench, step: CollaborationStep) -> DepartmentWorkbench:
    """向工作台追加一条协作步骤。"""
    return DepartmentWorkbench(
        thread_id=workbench.thread_id,
        original_user_input=workbench.original_user_input,
        collaboration_steps=[*workbench.collaboration_steps, step],
    )


class DepartmentWorkbenchService:
    """管理部门共享工作台。

    共享工作台是"DeerFlow 原生协作过程"的单一事实来源。它不参与角色决策，
    只负责保存当前回合的用户任务和需要展示给用户的协作摘要。

    阶段 4 重定义：原 reserve_collaboration 机制（限制角色协作次数）已移除，
    原因：DeerFlow 原生 task/subagent 的内部执行不经过自写协作层，
    因此无法在应用层拦截其协作次数。"协作次数"概念在 DeerFlow runtime
    内部受 DeerFlow 自己管理。
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

    def record_collaboration_step(self, thread_id: str, step: CollaborationStep) -> None:
        """记录一条协作步骤。"""
        workbench = self._require_workbench(thread_id)
        self._repository.save(_append_step(workbench, step))

    def list_collaboration_steps(self, thread_id: str) -> list[CollaborationStep]:
        """读取当前回合全部协作步骤。"""
        return list(self._require_workbench(thread_id).collaboration_steps)

    def get_original_user_input(self, thread_id: str) -> str:
        """读取当前回合原始用户输入。"""
        return self._require_workbench(thread_id).original_user_input

    def _require_workbench(self, thread_id: str) -> DepartmentWorkbench:
        """读取工作台并确保其存在。"""
        workbench = self._repository.get(thread_id)
        if workbench is None:
            raise DepartmentError("当前线程尚未初始化财务部门工作台")
        return workbench
