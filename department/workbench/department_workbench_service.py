"""财务部门共享工作台服务。

支持两种持久化策略：
- CLI 轻量路径：InMemoryDepartmentWorkbenchRepository（每次 start_turn 创建新实例）
- API 多回合路径：SQLiteDepartmentWorkbenchRepository（每次 finalize_turn 保存到 DB）
"""

from department.department_error import DepartmentError
from department.llm_usage import LlmUsage
from department.workbench.collaboration_step import CollaborationStep
from department.workbench.department_workbench import DepartmentWorkbench
from department.workbench.department_workbench_repository import DepartmentWorkbenchRepository
from department.workbench.execution_event import ExecutionEvent


class DepartmentWorkbenchService:
    """管理部门共享工作台。

    共享工作台是"DeerFlow 原生协作过程"的单一事实来源。它不参与角色决策，
    只负责保存当前回合的用户任务和需要展示给用户的协作摘要。

    注意：当前实现中，execution_events 不经过 in-memory 工作台，
    直接由 FinanceDepartmentService 在调用 finalize_turn() 时传入。
    这样设计是因为 execution_events 产生于 DeerFlow stream 解析，
    在 FinanceDepartmentService 层已有完整数据。
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
        """向当前回合工作台追加一条协作步骤。"""
        workbench = self._require_workbench(thread_id)
        self._repository.save(
            DepartmentWorkbench(
                thread_id=workbench.thread_id,
                original_user_input=workbench.original_user_input,
                collaboration_steps=[*workbench.collaboration_steps, step],
                reply_text=workbench.reply_text,
                usage=workbench.usage,
            )
        )

    def finalize_turn(
        self,
        thread_id: str,
        reply_text: str,
        usage: LlmUsage | None,
        execution_events: list[ExecutionEvent] | None = None,
    ) -> None:
        """结束当前回合，保存最终回复和 token 使用量。

        Args:
            thread_id: 线程标识。
            reply_text: DeerFlow 最终回复文本。
            usage: LLM token 使用量（可为 None）。
            execution_events: 内部执行事件列表（来自 DeerFlow stream 解析，
                不暴露给用户，但会持久化用于审计查询）。
        """
        workbench = self._require_workbench(thread_id)
        # execution_events 为 None 时使用空列表（CLI 轻量路径）
        evts = execution_events if execution_events is not None else []
        self._repository.save_turn(
            thread_id=thread_id,
            original_user_input=workbench.original_user_input,
            reply_text=reply_text,
            usage=usage,
            collaboration_steps=workbench.collaboration_steps,
            execution_events=evts,
        )

    def list_collaboration_steps(self, thread_id: str) -> list[CollaborationStep]:
        """读取当前线程全部回合的协作步骤（扁平列表）。"""
        return self._repository.list_collaboration_steps(thread_id)

    def list_execution_events_with_context(self, thread_id: str) -> list[dict]:
        """读取当前线程全部回合的内部执行事件（含回合归属上下文）。"""
        return self._repository.list_execution_events_with_context(thread_id)

    def list_turns_with_steps(self, thread_id: str) -> list[dict]:
        """读取当前线程全部回合（含每轮的协作步骤）。"""
        return self._repository.list_turns_with_steps(thread_id)

    def _require_workbench(self, thread_id: str) -> DepartmentWorkbench:
        """读取工作台并确保其存在。"""
        workbench = self._repository.get(thread_id)
        if workbench is None:
            raise DepartmentError("当前线程尚未初始化财务部门工作台")
        return workbench
