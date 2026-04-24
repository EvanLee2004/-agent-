"""crewAI 凭证审核工具。"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from department.workbench.execution_event import ExecutionEvent
from department.workbench.execution_event_type import ExecutionEventType
from runtime.crewai.accounting_tool_context_registry import AccountingToolContextRegistry
from runtime.crewai.execution_event_scope import append_execution_event


class AuditVoucherTool(BaseTool):
    """审核凭证风险。"""

    class InputSchema(BaseModel):
        """审核工具入参。"""

        target: str = Field(..., description="latest、all 或 voucher_id")
        voucher_id: int | None = Field(default=None, description="target=voucher_id 时填写")

    name: str = "audit_voucher"
    description: str = "审核最新、全部或指定会计凭证的借贷平衡、异常金额和摘要质量风险。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行审核工具。"""
        payload = self.InputSchema.model_validate(kwargs)
        arguments = {
            "target": payload.target,
            "voucher_id": payload.voucher_id,
        }
        append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.TOOL_CALL,
                tool_name=self.name,
                summary=f"调用 {self.name}",
            )
        )
        response = AccountingToolContextRegistry.get_context().audit_voucher_router.route(
            arguments
        )
        append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.TOOL_RESULT,
                tool_name=self.name,
                summary=response.to_tool_message_content(),
            )
        )
        return response.to_tool_message_content()


audit_voucher_tool = AuditVoucherTool()
