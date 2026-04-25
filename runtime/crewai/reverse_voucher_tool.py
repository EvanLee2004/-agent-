"""crewAI 凭证红冲工具。"""

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


class ReverseVoucherTool(BaseTool):
    """为已过账凭证生成红冲凭证。"""

    class InputSchema(BaseModel):
        """凭证红冲入参。"""

        voucher_id: int = Field(..., description="待红冲原凭证 ID")
        reversal_date: str | None = Field(default=None, description="红冲日期 YYYY-MM-DD")

    name: str = "reverse_voucher"
    description: str = "为已过账凭证创建借贷方向相反的红冲凭证。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行凭证红冲工具。"""
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
        response = (
            AccountingToolContextRegistry.get_context()
            .reverse_voucher_router
            .route(arguments)
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


reverse_voucher_tool = ReverseVoucherTool()
