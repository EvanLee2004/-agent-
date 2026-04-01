"""工具路由接口。"""

from abc import ABC, abstractmethod

from conversation.tool_definition import ToolDefinition
from conversation.tool_router_response import ToolRouterResponse


class ToolRouter(ABC):
    """工具路由接口。"""

    @abstractmethod
    def get_definition(self) -> ToolDefinition:
        """返回工具定义。

        Returns:
            当前工具的定义对象。
        """
        raise NotImplementedError

    @abstractmethod
    def route(self, arguments: dict) -> ToolRouterResponse:
        """处理工具调用。

        Args:
            arguments: 已解析好的工具参数。

        Returns:
            工具执行结果。
        """
        raise NotImplementedError
