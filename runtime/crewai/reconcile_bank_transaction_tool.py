"""crewAI 银行流水对账工具。"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from department.workbench.execution_event import ExecutionEvent
from department.workbench.execution_event_type import ExecutionEventType
from runtime.crewai.accounting_tool_context_registry import AccountingToolContextRegistry
from runtime.crewai.execution_event_scope import append_execution_event


class ReconcileBankTransactionTool(BaseTool):
    """标记银行流水已对账。"""

    class InputSchema(BaseModel):
        """银行流水对账入参。"""

        transaction_id: int = Field(..., description="银行流水 ID")
        linked_voucher_id: int | None = Field(
            default=None,
            description="可选关联凭证 ID",
        )

    name: str = "reconcile_bank_transaction"
    description: str = "把银行流水标记为已对账，可选关联已经确认的总账凭证。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行银行流水对账工具。"""
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
            .reconcile_bank_transaction_router
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


reconcile_bank_transaction_tool = ReconcileBankTransactionTool()
