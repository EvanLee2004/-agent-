"""工具注册表。

注册表的职责很单纯：
- 管理工具定义
- 根据名称找到对应 handler
- 把 handler 暴露为 runtime 可消费的统一接口
"""

from abc import ABC, abstractmethod
from typing import Optional

from tools.schemas import ToolDefinition, ToolExecutionResult


class ToolHandler(ABC):
    """工具处理器抽象基类。"""

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """返回工具定义。"""
        pass

    @abstractmethod
    def execute(self, arguments: dict) -> ToolExecutionResult:
        """执行工具。"""
        pass


class ToolRegistry:
    """工具注册表。"""

    def __init__(self):
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, handler: ToolHandler) -> None:
        """注册单个工具处理器。"""
        self._handlers[handler.definition.name] = handler

    def get_handler(self, tool_name: str) -> Optional[ToolHandler]:
        """按工具名获取处理器。"""
        return self._handlers.get(tool_name)

    def get_openai_tools(self) -> list[dict]:
        """获取 provider 可直接使用的工具定义列表。"""
        return [
            handler.definition.to_openai_tool()
            for handler in self._handlers.values()
        ]

    def execute(self, tool_name: str, arguments: dict) -> ToolExecutionResult:
        """执行指定工具。"""
        handler = self.get_handler(tool_name)
        if handler is None:
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                error_message=f"未注册工具: {tool_name}",
            )
        return handler.execute(arguments)
