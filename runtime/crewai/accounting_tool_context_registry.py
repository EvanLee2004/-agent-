"""crewAI 会计工具上下文注册器。"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from department.department_error import DepartmentError
from runtime.crewai.accounting_tool_context import AccountingToolContext


_CURRENT_ACCOUNTING_TOOL_CONTEXT: ContextVar[AccountingToolContext | None] = ContextVar(
    "CURRENT_ACCOUNTING_TOOL_CONTEXT",
    default=None,
)


class AccountingToolContextRegistry:
    """为 crewAI 工具提供请求级业务上下文。

    crewAI 的工具签名只包含模型生成的工具参数，不会自动带上数据库仓储、
    业务 service 或当前请求范围。这里用 ContextVar 把“当前请求使用哪套
    会计路由”显式绑定到调用栈，避免工具包装器退回到模块级全局变量。
    """

    @classmethod
    @contextmanager
    def open_context_scope(
        cls,
        context: AccountingToolContext,
    ) -> Iterator[None]:
        """打开会计工具上下文作用域。"""
        token = _CURRENT_ACCOUNTING_TOOL_CONTEXT.set(context)
        try:
            yield
        finally:
            _CURRENT_ACCOUNTING_TOOL_CONTEXT.reset(token)

    @classmethod
    def get_context(cls) -> AccountingToolContext:
        """读取当前请求的会计工具上下文。"""
        context = _CURRENT_ACCOUNTING_TOOL_CONTEXT.get()
        if context is None:
            raise DepartmentError("当前没有可用的会计工具上下文")
        return context
