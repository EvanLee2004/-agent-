"""crewAI 会计科目查询工具。"""

from crewai.tools import BaseTool
from pydantic import BaseModel

from department.workbench.execution_event import ExecutionEvent
from department.workbench.execution_event_type import ExecutionEventType
from runtime.crewai.accounting_tool_context_registry import AccountingToolContextRegistry
from runtime.crewai.execution_event_scope import append_execution_event


class QueryChartOfAccountsTool(BaseTool):
    """查询当前账簿可用科目。"""

    class InputSchema(BaseModel):
        """会计科目查询工具入参。"""

    name: str = "query_chart_of_accounts"
    description: str = "查询当前系统允许使用的会计科目编码、名称、类别和说明。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行科目查询工具。"""
        append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.TOOL_CALL,
                tool_name=self.name,
                summary=f"调用 {self.name}",
            )
        )
        response = (
            AccountingToolContextRegistry.get_context()
            .query_chart_of_accounts_router
            .route({})
        )
        append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.TOOL_RESULT,
                tool_name=self.name,
                summary=response.to_tool_message_content(),
            )
        )
        return response.to_tool_message_content()


query_chart_of_accounts_tool = QueryChartOfAccountsTool()
