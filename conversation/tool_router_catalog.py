"""工具路由目录。"""

from typing import Optional

from conversation.tool_router import ToolRouter


class ToolRouterCatalog:
    """工具路由目录。"""

    def __init__(self, tool_routers: list[ToolRouter]):
        self._tool_routers = {tool_router.get_definition().name: tool_router for tool_router in tool_routers}

    def list_tool_definitions(self) -> list[dict]:
        """列出全部工具定义。

        Returns:
            provider 可直接消费的工具定义列表。
        """
        return [
            tool_router.get_definition().to_openai_tool()
            for tool_router in self._tool_routers.values()
        ]

    def get_tool_router(self, tool_name: str) -> Optional[ToolRouter]:
        """按名称读取工具路由。

        Args:
            tool_name: 工具名。

        Returns:
            对应工具路由；不存在时返回 `None`。
        """
        return self._tool_routers.get(tool_name)
