"""crewAI 总账/明细账查询工具。"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from department.workbench.execution_event import ExecutionEvent
from department.workbench.execution_event_type import ExecutionEventType
from runtime.crewai.accounting_tool_context_registry import AccountingToolContextRegistry
from runtime.crewai.execution_event_scope import append_execution_event


class QueryLedgerEntriesTool(BaseTool):
    """查询总账或明细账行。"""

    class InputSchema(BaseModel):
        """账簿明细查询入参。"""

        period_name: str | None = Field(default=None, description="可选会计期间 YYYYMM")
        subject_code: str | None = Field(default=None, description="可选科目编码")
        limit: int = Field(default=200, description="最大返回行数")

    name: str = "query_ledger_entries"
    description: str = "查询已过账凭证形成的总账/明细账。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行账簿明细查询工具。"""
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
            .query_ledger_entries_router
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


query_ledger_entries_tool = QueryLedgerEntriesTool()
