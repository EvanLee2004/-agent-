"""查账 LangChain 工具。"""

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from runtime.deerflow.finance_department_tool_context_registry import FinanceDepartmentToolContextRegistry


class QueryVouchersTool(BaseTool):
    """查询已入账的凭证。"""

    class InputSchema(BaseModel):
        """查账工具入参。"""

        date: str | None = Field(default=None, description="可选日期过滤，例如 2024-03 或 2024-03-01")
        status: str | None = Field(default=None, description="可选状态过滤，例如 pending 或 approved")
        limit: int = Field(default=20, description="最大返回条数，默认 20")

    name: str = "query_vouchers"
    description: str = "查询已入账的凭证列表，可按日期和状态过滤。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行查账工具。"""
        payload = self.InputSchema.model_validate(kwargs)
        router = FinanceDepartmentToolContextRegistry.get_context().query_vouchers_router
        arguments = {"limit": payload.limit}
        if payload.date:
            arguments["date"] = payload.date
        if payload.status:
            arguments["status"] = payload.status
        response = router.route(
            arguments
        )
        return response.to_tool_message_content()


query_vouchers_tool = QueryVouchersTool()
