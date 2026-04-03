"""查记忆工具入口。"""

from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse
from memory.memory_service import MemoryService
from memory.search_memory_query import SearchMemoryQuery


DEFAULT_MEMORY_SEARCH_LIMIT = 5


def _build_search_query(arguments: dict) -> SearchMemoryQuery:
    """把工具参数转换为记忆搜索查询。"""
    return SearchMemoryQuery(
        query=str(arguments["query"]).strip(),
        limit=int(arguments.get("limit", DEFAULT_MEMORY_SEARCH_LIMIT) or DEFAULT_MEMORY_SEARCH_LIMIT),
    )


def _serialize_search_item(item) -> dict:
    """序列化单条记忆搜索结果。"""
    return {
        "path": item.path,
        "scope": item.scope.value,
        "category": item.category,
        "content": item.content,
        "start_line": item.start_line,
        "end_line": item.end_line,
        "score": item.score,
    }


def _build_payload(results: list) -> dict:
    """构造记忆搜索工具返回值。"""
    return {
        "count": len(results),
        "items": [_serialize_search_item(item) for item in results],
    }


class SearchMemoryRouter(ToolRouter):
    """查记忆工具入口。"""

    def __init__(self, memory_service: MemoryService):
        self._memory_service = memory_service

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行查记忆。"""
        search_query = _build_search_query(arguments)
        results = self._memory_service.search_memory(search_query)
        return ToolRouterResponse(
            tool_name="search_memory",
            success=True,
            payload=_build_payload(results),
        )
