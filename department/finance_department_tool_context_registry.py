"""财务部门工具上下文注册器。"""

from typing import Optional

from department.finance_department_tool_context import FinanceDepartmentToolContext


class FinanceDepartmentToolContextRegistry:
    """保存 DeerFlow 工具可见的财务部门上下文。

    这是受 DeerFlow 静态工具装配协议约束而保留的唯一全局注册点。之所以把它留在
    部门模块，而不是会话模块，是为了明确表达：这层副作用是“部门运行时资产”的一部分，
    不属于对外会话协议。
    """

    _context: Optional[FinanceDepartmentToolContext] = None

    @classmethod
    def register(cls, context: FinanceDepartmentToolContext) -> None:
        """注册当前运行时的财务部门工具上下文。

        Args:
            context: 已完成依赖装配的财务部门工具上下文。
        """
        cls._context = context

    @classmethod
    def get_context(cls) -> FinanceDepartmentToolContext:
        """获取当前财务部门工具上下文。

        Returns:
            当前已注册的工具上下文。

        Raises:
            RuntimeError: 注册前访问时抛出。
        """
        if cls._context is None:
            raise RuntimeError("财务部门工具上下文尚未注册，DeerFlow 工具暂不可用")
        return cls._context

    @classmethod
    def reset(cls) -> None:
        """重置当前上下文。

        该方法只用于测试清理，避免跨测试共享全局状态。
        """
        cls._context = None
