"""crewAI 查账工具。"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from department.workbench.execution_event import ExecutionEvent
from department.workbench.execution_event_type import ExecutionEventType
from runtime.crewai.accounting_tool_context_registry import AccountingToolContextRegistry
from runtime.crewai.execution_event_scope import append_execution_event


class QueryVouchersTool(BaseTool):
    """查询会计凭证。"""

    class InputSchema(BaseModel):
        """查账工具入参。"""

        date: str | None = Field(default=None, description="可选日期过滤，例如 2024-03")
        status: str | None = Field(default=None, description="可选状态，例如 pending")
        limit: int = Field(default=20, description="最大返回条数")

    name: str = "query_vouchers"
    description: str = "查询已入账的会计凭证，支持日期、状态和数量过滤。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行查账工具。"""
        payload = self.InputSchema.model_validate(kwargs)
        arguments = {"limit": payload.limit}
        if payload.date:
            arguments["date"] = payload.date
        if payload.status:
            arguments["status"] = payload.status
        append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.TOOL_CALL,
                tool_name=self.name,
                summary=f"调用 {self.name}",
            )
        )
        response = AccountingToolContextRegistry.get_context().query_vouchers_router.route(
            arguments
        )
        append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.TOOL_RESULT,
                tool_name=self.name,
                summary=response.to_tool_message_content(),
            )
        )
        return response.to_tool_message_content()


query_vouchers_tool = QueryVouchersTool()
