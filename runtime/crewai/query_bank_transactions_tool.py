"""crewAI 银行流水查询工具。"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from department.workbench.execution_event import ExecutionEvent
from department.workbench.execution_event_type import ExecutionEventType
from runtime.crewai.accounting_tool_context_registry import AccountingToolContextRegistry
from runtime.crewai.execution_event_scope import append_execution_event


class QueryBankTransactionsTool(BaseTool):
    """查询出纳/银行流水。"""

    class InputSchema(BaseModel):
        """银行流水查询入参。"""

        date: str | None = Field(default=None, description="可选日期前缀，例如 2024-03")
        status: str | None = Field(default=None, description="unreconciled 或 reconciled")
        direction: str | None = Field(default=None, description="inflow 或 outflow")
        limit: int = Field(default=20, description="最大返回条数")

    name: str = "query_bank_transactions"
    description: str = "查询银行流水，支持日期、方向、对账状态和数量过滤。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行银行流水查询工具。"""
        payload = self.InputSchema.model_validate(kwargs)
        arguments = {
            "date": payload.date,
            "status": payload.status,
            "direction": payload.direction,
            "limit": payload.limit,
        }
        append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.TOOL_CALL,
                tool_name=self.name,
                summary=f"调用 {self.name}",
            )
        )
        response = (
            AccountingToolContextRegistry.get_context()
            .query_bank_transactions_router
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


query_bank_transactions_tool = QueryBankTransactionsTool()
