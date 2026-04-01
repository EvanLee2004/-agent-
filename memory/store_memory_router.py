"""写记忆工具入口。"""

from conversation.tool_definition import ToolDefinition
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse
from memory.memory_error import MemoryError
from memory.memory_scope import MemoryScope
from memory.memory_service import MemoryService
from memory.store_memory_command import StoreMemoryCommand


STORE_MEMORY_PARAMETERS = {
    "type": "object",
    "properties": {
        "scope": {"type": "string", "enum": ["long_term", "daily"]},
        "category": {"type": "string"},
        "content": {"type": "string"},
    },
    "required": ["scope", "category", "content"],
}


def _build_store_command(arguments: dict) -> StoreMemoryCommand:
    """把工具参数转换为记忆写入命令。"""
    return StoreMemoryCommand(
        scope=MemoryScope(str(arguments["scope"]).strip()),
        category=str(arguments["category"]).strip(),
        content=str(arguments["content"]).strip(),
    )


def _build_success_payload(command: StoreMemoryCommand) -> dict:
    """构造记忆写入成功结果。"""
    return {
        "stored": True,
        "scope": command.scope.value,
        "category": command.category,
        "content": command.content,
    }


class StoreMemoryRouter(ToolRouter):
    """写记忆工具入口。"""

    def __init__(self, memory_service: MemoryService):
        self._memory_service = memory_service

    def get_definition(self) -> ToolDefinition:
        """返回工具定义。"""
        return ToolDefinition(
            name="store_memory",
            description="把用户明确要求记住的偏好、事实或短期上下文写入记忆。只有成功调用本工具写入的内容，才算系统已经真正记住。",
            parameters=STORE_MEMORY_PARAMETERS,
        )

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行写记忆。"""
        try:
            command = _build_store_command(arguments)
            self._memory_service.store_memory(command)
            return ToolRouterResponse(
                tool_name="store_memory",
                success=True,
                payload=_build_success_payload(command),
            )
        except (KeyError, ValueError, MemoryError) as error:
            return ToolRouterResponse(
                tool_name="store_memory",
                success=False,
                error_message=f"记忆参数无效: {str(error)}",
            )
