"""crewAI 银行流水记录工具。"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from department.department_runtime_context import CURRENT_THREAD_ID
from department.workbench.execution_event import ExecutionEvent
from department.workbench.execution_event_type import ExecutionEventType
from runtime.crewai.accounting_tool_context_registry import AccountingToolContextRegistry
from runtime.crewai.execution_event_scope import append_execution_event
from runtime.crewai.idempotency_tracker import (
    check_idempotency,
    compute_idempotency_key,
    record_idempotency,
)


class RecordBankTransactionTool(BaseTool):
    """记录出纳/银行流水。"""

    class InputSchema(BaseModel):
        """银行流水记录入参。"""

        transaction_date: str = Field(..., description="流水日期，格式 YYYY-MM-DD")
        direction: str = Field(..., description="inflow 或 outflow")
        amount: float = Field(..., description="流水金额，必须大于 0")
        account_name: str = Field(..., description="银行账户或现金账户名称")
        counterparty: str = Field(default="", description="对方单位或个人")
        summary: str = Field(..., description="流水摘要")

    name: str = "record_bank_transaction"
    description: str = "记录银行收付款流水；不会自动生成总账凭证。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行银行流水记录工具。

        银行流水记录和凭证录入一样是写操作。crewAI 可能因为模型重试或服务调用重放
        再次触发同一工具参数，因此这里复用持久化幂等表，确保同一 thread 内的同一笔
        流水只落库一次。
        """
        payload = self.InputSchema.model_validate(kwargs)
        arguments = payload.model_dump()
        append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.TOOL_CALL,
                tool_name=self.name,
                summary=f"调用 {self.name}",
            )
        )

        thread_id = CURRENT_THREAD_ID.get() or "default"
        idempotency_key = compute_idempotency_key(thread_id, self.name, arguments)
        cached_response = check_idempotency(idempotency_key)
        if cached_response is not None:
            append_execution_event(
                ExecutionEvent(
                    event_type=ExecutionEventType.TOOL_RESULT,
                    tool_name=self.name,
                    summary=cached_response.to_tool_message_content(),
                )
            )
            return cached_response.to_tool_message_content()

        response = (
            AccountingToolContextRegistry.get_context()
            .record_bank_transaction_router
            .route(arguments)
        )
        record_idempotency(idempotency_key, response)
        append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.TOOL_RESULT,
                tool_name=self.name,
                summary=response.to_tool_message_content(),
            )
        )
        return response.to_tool_message_content()


record_bank_transaction_tool = RecordBankTransactionTool()
