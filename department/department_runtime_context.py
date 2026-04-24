"""会计部门运行时上下文。"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator


CURRENT_THREAD_ID: ContextVar[str | None] = ContextVar(
    "CURRENT_THREAD_ID",
    default=None,
)


class DepartmentRuntimeContext:
    """保存当前会计部门调用的线程上下文。

    crewAI 工具执行发生在同一 Python 进程里，但工具函数签名只包含模型生成的
    业务参数，不会自动带上当前 thread_id。当前会计部门只需要 thread_id 做写工具
    幂等保护，因此这里刻意不再保存角色名、协作深度等冗余上下文，避免运行时层
    看起来像在维护另一套协作状态。
    """

    @contextmanager
    def open_scope(
        self,
        thread_id: str,
    ) -> Iterator[None]:
        """打开一次会计部门运行范围。

        Args:
            thread_id: 当前线程标识。
        """
        thread_token = CURRENT_THREAD_ID.set(thread_id)
        try:
            yield
        finally:
            CURRENT_THREAD_ID.reset(thread_token)
