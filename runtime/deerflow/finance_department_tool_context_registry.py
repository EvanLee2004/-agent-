"""DeerFlow 财务部门工具上下文注册器。"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

from runtime.deerflow.finance_department_tool_context import FinanceDepartmentToolContext


# 使用 contextvars 实现线程/协程安全的上下文存储
_CURRENT_CONTEXT: ContextVar[Optional[FinanceDepartmentToolContext]] = ContextVar(
    "_CURRENT_CONTEXT", default=None
)


class FinanceDepartmentToolContextRegistry:
    """保存 DeerFlow 工具可见的财务部门上下文。

    使用 contextvars 实现，线程/协程安全，避免全局可变状态问题。
    通过 contextmanager 管理上下文生命周期，确保不会泄露到其他测试或请求。
    """

    @classmethod
    def register(cls, context: FinanceDepartmentToolContext) -> None:
        """注册当前运行时的财务部门工具上下文。

        Args:
            context: 已完成依赖装配的财务部门工具上下文。
        """
        _CURRENT_CONTEXT.set(context)

    @classmethod
    def get_context(cls) -> FinanceDepartmentToolContext:
        """获取当前财务部门工具上下文。

        Returns:
            当前已注册的工具上下文。

        Raises:
            RuntimeError: 注册前访问时抛出。
        """
        context = _CURRENT_CONTEXT.get()
        if context is None:
            raise RuntimeError("财务部门工具上下文尚未注册，DeerFlow 工具暂不可用")
        return context

    @classmethod
    def reset(cls) -> None:
        """重置当前上下文。

        该方法只用于测试清理，避免跨测试共享状态。
        """
        _CURRENT_CONTEXT.set(None)

    @classmethod
    @contextmanager
    def open_context_scope(
        cls,
        context: FinanceDepartmentToolContext,
    ) -> Iterator[None]:
        """打开一个上下文作用域。

        上下文在作用域结束时自动重置，适合测试和请求级别的生命周期管理。

        Args:
            context: 财务部门工具上下文。
        """
        token = _CURRENT_CONTEXT.set(context)
        try:
            yield
        finally:
            _CURRENT_CONTEXT.reset(token)
