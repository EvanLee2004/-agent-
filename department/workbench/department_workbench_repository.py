"""财务部门工作台仓储接口。"""

from abc import ABC, abstractmethod
from typing import Optional

from department.llm_usage import LlmUsage
from department.workbench.collaboration_step import CollaborationStep
from department.workbench.department_workbench import DepartmentWorkbench
from department.workbench.execution_event import ExecutionEvent


class DepartmentWorkbenchRepository(ABC):
    """定义工作台仓储接口。

    当前仓储接口的核心目标，是把“当前回合暂存”和“多回合历史落库”这两个阶段
    通过统一契约表达出来。当前真实实现只有 SQLiteDepartmentWorkbenchRepository，
    因此接口不再保留默认 fallback 语义，避免继续为已删除的轻量兼容实现续命。

    接口分两组：
    1. 当前回合暂存方法（save/get）：用于 start_turn 到 finalize_turn 之间的累积
    2. 多回合历史方法（save_turn/list_turns_with_steps 等）：生产路径依赖
    """

    @abstractmethod
    def save(self, workbench: DepartmentWorkbench) -> None:
        """保存当前线程的工作台暂存态。

        设计原因：
        DeerFlow stream 事件是逐步投影为协作步骤的，因此在最终回复落库前，
        需要一个“当前回合暂存区”累积步骤。SQLite 实现中，此方法只写 pending
        workbench；真正的历史持久化由 finalize_turn -> save_turn() 负责。
        """

    @abstractmethod
    def get(self, thread_id: str) -> Optional[DepartmentWorkbench]:
        """读取某个线程当前回合的工作台。

        Returns:
            当前线程的工作台；不存在时返回 None。
        """

    @abstractmethod
    def save_turn(
        self,
        thread_id: str,
        original_user_input: str,
        reply_text: str,
        usage: LlmUsage | None,
        collaboration_steps: list[CollaborationStep],
        execution_events: list[ExecutionEvent],
    ) -> None:
        """保存一轮完整对话（多回合接口）。"""

    @abstractmethod
    def list_turns_with_steps(self, thread_id: str) -> list[dict]:
        """列出某线程全部回合（含每轮的协作步骤）。"""

    @abstractmethod
    def list_collaboration_steps(self, thread_id: str) -> list[CollaborationStep]:
        """列出某线程全部回合的协作步骤。"""

    @abstractmethod
    def list_execution_events_with_context(self, thread_id: str) -> list[dict]:
        """列出某线程全部回合的内部执行事件（含回合归属上下文）。"""

    @abstractmethod
    def clear_thread(self, thread_id: str) -> None:
        """清除某线程全部历史。

        用途说明：此方法仅用于测试场景清理，不属于生产 API。
        生产路径中没有主动清除线程历史的需求（历史通过 turn_index 累积）。
        """
