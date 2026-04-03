"""查记忆 LangChain 工具。"""

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from runtime.deerflow.finance_department_tool_context_registry import FinanceDepartmentToolContextRegistry


class SearchMemoryTool(BaseTool):
    """查询项目记忆中的相关片段。"""

    class InputSchema(BaseModel):
        """查记忆工具入参。"""

        query: str = Field(..., description="用于查找相关记忆的查询文本")
        limit: int = Field(default=5, description="最大返回条数，默认 5")

    name: str = "search_memory"
    description: str = "搜索与当前问题相关的长期或每日记忆片段。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行查记忆工具。"""
        payload = self.InputSchema.model_validate(kwargs)
        router = FinanceDepartmentToolContextRegistry.get_context().search_memory_router
        response = router.route(
            {
                "query": payload.query,
                "limit": payload.limit,
            }
        )
        return response.to_tool_message_content()


search_memory_tool = SearchMemoryTool()
