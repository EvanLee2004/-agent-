"""写记忆 LangChain 工具。"""

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from runtime.deerflow.finance_department_tool_context_registry import FinanceDepartmentToolContextRegistry


class StoreMemoryTool(BaseTool):
    """把用户明确要求记住的信息写入项目记忆。"""

    class InputSchema(BaseModel):
        """写记忆工具入参。"""

        scope: str = Field(..., description="必须为 long_term 或 daily")
        category: str = Field(..., description="记忆类别，例如 preference、fact、decision")
        content: str = Field(..., description="需要写入记忆的内容")

    name: str = "store_memory"
    description: str = "把用户明确要求记住的偏好、事实或短期上下文写入记忆。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行写记忆工具。"""
        payload = self.InputSchema.model_validate(kwargs)
        router = FinanceDepartmentToolContextRegistry.get_context().store_memory_router
        response = router.route(
            {
                "scope": payload.scope,
                "category": payload.category,
                "content": payload.content,
            }
        )
        return response.to_tool_message_content()


store_memory_tool = StoreMemoryTool()
