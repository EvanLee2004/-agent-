"""财务部门运行时上下文。"""

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator, Optional

from department.department_error import DepartmentError


CURRENT_ROLE_NAME: ContextVar[Optional[str]] = ContextVar("CURRENT_ROLE_NAME", default=None)
CURRENT_THREAD_ID: ContextVar[Optional[str]] = ContextVar("CURRENT_THREAD_ID", default=None)
CURRENT_COLLABORATION_DEPTH: ContextVar[int] = ContextVar("CURRENT_COLLABORATION_DEPTH", default=0)


class DepartmentRuntimeContext:
    """保存当前角色调用的线程上下文。

    DeerFlow 工具执行发生在同一 Python 进程里，但工具函数签名并不会自动带上
    “当前是谁在调用、属于哪条线程、当前协作深度是多少”。这层上下文把这些最小
    必要事实显式暴露出来，供协作工具读取，同时避免把角色信息塞回全局单例。
    """

    @contextmanager
    def open_scope(
        self,
        role_name: str,
        thread_id: str,
        collaboration_depth: int,
    ) -> Iterator[None]:
        """打开一次角色执行范围。

        Args:
            role_name: 当前执行角色。
            thread_id: 当前线程标识。
            collaboration_depth: 当前协作深度。
        """
        role_token = CURRENT_ROLE_NAME.set(role_name)
        thread_token = CURRENT_THREAD_ID.set(thread_id)
        depth_token = CURRENT_COLLABORATION_DEPTH.set(collaboration_depth)
        try:
            yield
        finally:
            CURRENT_ROLE_NAME.reset(role_token)
            CURRENT_THREAD_ID.reset(thread_token)
            CURRENT_COLLABORATION_DEPTH.reset(depth_token)

    def require_current_role_name(self) -> str:
        """获取当前执行角色名。

        Returns:
            当前角色名。

        Raises:
            DepartmentError: 当前没有角色上下文时抛出。
        """
        role_name = CURRENT_ROLE_NAME.get()
        if not role_name:
            raise DepartmentError("当前没有可用的财务角色上下文")
        return role_name

    def require_current_thread_id(self) -> str:
        """获取当前线程标识。

        Returns:
            当前线程标识。

        Raises:
            DepartmentError: 当前没有线程上下文时抛出。
        """
        thread_id = CURRENT_THREAD_ID.get()
        if not thread_id:
            raise DepartmentError("当前没有可用的线程上下文")
        return thread_id

    def get_current_collaboration_depth(self) -> int:
        """获取当前协作深度。"""
        return CURRENT_COLLABORATION_DEPTH.get()

