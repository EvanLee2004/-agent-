"""财务部门工作台仓储接口。"""

from abc import ABC, abstractmethod
from typing import Optional

from department.llm_usage import LlmUsage
from department.workbench.collaboration_step import CollaborationStep
from department.workbench.department_workbench import DepartmentWorkbench
from department.workbench.execution_event import ExecutionEvent


class DepartmentWorkbenchRepository(ABC):
    """定义工作台仓储接口。

    支持两种实现：
    - InMemoryDepartmentWorkbenchRepository：CLI 轻量路径，每次 start_turn 新建实例
    - SQLiteDepartmentWorkbenchRepository：API 多回合路径，支持历史查询

    接口分两组：
    1. 兼容性方法（save/get）：保留用于 CLI 路径兼容
    2. 多回合方法（save_turn/list_turns_with_steps 等）：API 路径使用，SQLite 实现有完整逻辑
    """

    @abstractmethod
    def save(self, workbench: DepartmentWorkbench) -> None:
        """保存当前线程的工作台（CLI 兼容性方法）。

        CLI 路径使用：每次 start_turn 创建新 workbench 并 save。
        API 路径：SQLite 实现中此方法只写内存 pending，由 finalize_turn 调用 save_turn() 落库。
        """

    @abstractmethod
    def get(self, thread_id: str) -> Optional[DepartmentWorkbench]:
        """读取某个线程当前回合的工作台（兼容性方法）。

        Returns:
            当前线程的工作台；不存在时返回 None。
        """

    def save_turn(
        self,
        thread_id: str,
        original_user_input: str,
        reply_text: str,
        usage: LlmUsage | None,
        collaboration_steps: list[CollaborationStep],
        execution_events: list[ExecutionEvent],
    ) -> None:
        """保存一轮完整对话（多回合接口）。

        默认实现调用 save()` 模拟，用于 InMemory 实现。
        SQLite 实现override 此方法以支持真正的多回合持久化。
        """
        # In-memory fallback：直接覆盖
        self.save(
            DepartmentWorkbench(
                thread_id=thread_id,
                original_user_input=original_user_input,
                collaboration_steps=collaboration_steps,
                reply_text=reply_text,
                usage=usage,
            )
        )

    def list_turns_with_steps(self, thread_id: str) -> list[dict]:
        """列出某线程全部回合（含每轮的协作步骤）。

        默认实现：若有 pending workbench 则以单回合形式返回。
        SQLite 实现override 以返回完整历史。
        """
        wb = self.get(thread_id)
        if wb is None:
            return []
        return [
            {
                "turn_id": thread_id,  # InMemory 无 turn_id 概念，用 thread_id 代替
                "turn_index": 1,
                "original_user_input": wb.original_user_input,
                "reply_text": wb.reply_text,
                "usage": wb.usage,
                "created_at": None,
                "collaboration_steps": list(wb.collaboration_steps),
            }
        ]

    def list_collaboration_steps(self, thread_id: str) -> list[CollaborationStep]:
        """列出某线程全部回合的协作步骤。

        默认从最新 workbench 读取（InMemory 实现）。
        SQLite 实现override 以返回完整历史。
        """
        wb = self.get(thread_id)
        if wb is None:
            return []
        return list(wb.collaboration_steps)

    def list_execution_events_with_context(self, thread_id: str) -> list[dict]:
        """列出某线程全部回合的内部执行事件（含回合归属上下文）。

        默认返回空列表（InMemory 实现不存储 events）。
        SQLite 实现override。
        """
        return []

    def clear_thread(self, thread_id: str) -> None:
        """清除某线程全部历史。

        用途说明：此方法仅用于测试场景清理，不属于生产 API。
        生产路径中没有主动清除线程历史的需求（历史通过 turn_index 累积）。
        """
        # 默认 no-op
