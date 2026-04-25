"""crewAI 科目余额查询工具。"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from department.workbench.execution_event import ExecutionEvent
from department.workbench.execution_event_type import ExecutionEventType
from runtime.crewai.accounting_tool_context_registry import AccountingToolContextRegistry
from runtime.crewai.execution_event_scope import append_execution_event


class QueryAccountBalanceTool(BaseTool):
    """查询科目余额表。"""

    class InputSchema(BaseModel):
        """科目余额查询入参。"""

        period_name: str | None = Field(default=None, description="可选会计期间 YYYYMM")

    name: str = "query_account_balance"
    description: str = "查询已过账凭证形成的科目余额表。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行科目余额查询工具。"""
        payload = self.InputSchema.model_validate(kwargs)
        arguments = payload.model_dump()
        append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.TOOL_CALL,
                tool_name=self.name,
                summary=f"调用 {self.name}",
            )
        )
        response = (
            AccountingToolContextRegistry.get_context()
            .query_account_balance_router
            .route(arguments)
        )
        append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.TOOL_RESULT,
                tool_name=self.name,
                summary=response.to_tool_message_content(),
            )
        )
        return response.to_tool_message_content()


query_account_balance_tool = QueryAccountBalanceTool()
