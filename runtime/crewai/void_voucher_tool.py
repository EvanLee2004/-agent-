"""crewAI 凭证作废工具。"""

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


class VoidVoucherTool(BaseTool):
    """作废未过账凭证。"""

    class InputSchema(BaseModel):
        """凭证作废入参。"""

        voucher_id: int = Field(..., description="待作废凭证 ID")

    name: str = "void_voucher"
    description: str = "作废未过账凭证；已过账凭证必须使用 reverse_voucher 红冲。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行凭证作废工具。"""
        payload = self.InputSchema.model_validate(kwargs)
        arguments = payload.model_dump()
        append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.TOOL_CALL,
                tool_name=self.name,
                summary=f"调用 {self.name}",
            )
        )
        key = compute_idempotency_key(
            CURRENT_THREAD_ID.get() or "default",
            self.name,
            arguments,
        )
        cached_response = check_idempotency(key)
        if cached_response is not None:
            append_execution_event(
                ExecutionEvent(
                    event_type=ExecutionEventType.TOOL_RESULT,
                    tool_name=self.name,
                    summary=cached_response.to_tool_message_content(),
                )
            )
            return cached_response.to_tool_message_content()
        response = AccountingToolContextRegistry.get_context().void_voucher_router.route(
            arguments
        )
        record_idempotency(key, response)
        append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.TOOL_RESULT,
                tool_name=self.name,
                summary=response.to_tool_message_content(),
            )
        )
        return response.to_tool_message_content()


void_voucher_tool = VoidVoucherTool()
