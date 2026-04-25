"""crewAI 凭证过账工具。"""

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


class PostVoucherTool(BaseTool):
    """将凭证过账到总账。"""

    class InputSchema(BaseModel):
        """凭证过账入参。"""

        voucher_id: int = Field(..., description="待过账凭证 ID")

    name: str = "post_voucher"
    description: str = "把审核或待处理凭证标记为已过账，过账后进入报表统计。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行凭证过账工具。"""
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
        response = AccountingToolContextRegistry.get_context().post_voucher_router.route(
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


post_voucher_tool = PostVoucherTool()
