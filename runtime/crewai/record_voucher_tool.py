"""crewAI 记账工具。"""

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


class RecordVoucherTool(BaseTool):
    """把结构化凭证参数写入会计账簿。"""

    class InputSchema(BaseModel):
        """记账工具入参。"""

        voucher_date: str = Field(..., description="凭证日期，格式 YYYY-MM-DD")
        summary: str = Field(..., description="业务摘要，简洁表达业务实质")
        source_text: str = Field(default="", description="原始业务描述")
        lines: list[dict] = Field(..., description="分录行，至少两条且借贷平衡")

    name: str = "record_voucher"
    description: str = (
        "将已经识别清楚的会计业务记录为标准凭证。调用前必须确认借贷科目、金额和日期。"
    )
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行记账工具。

        crewAI 只负责把参数传入工具；会计校验、科目校验和落库仍由 accounting
        业务层完成。这里额外做幂等保护，是因为记账属于写操作，模型重试不能导致重复入账。
        """
        payload = self.InputSchema.model_validate(kwargs)
        arguments = {
            "voucher_date": payload.voucher_date,
            "summary": payload.summary,
            "source_text": payload.source_text,
            "lines": payload.lines,
        }
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

        router = AccountingToolContextRegistry.get_context().record_voucher_router
        response = router.route(arguments)
        record_idempotency(idempotency_key, response)
        append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.TOOL_RESULT,
                tool_name=self.name,
                summary=response.to_tool_message_content(),
            )
        )
        return response.to_tool_message_content()


record_voucher_tool = RecordVoucherTool()
