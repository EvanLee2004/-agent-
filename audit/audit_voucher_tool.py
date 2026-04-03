"""审核 LangChain 工具。"""

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from department.finance_department_tool_context_registry import FinanceDepartmentToolContextRegistry


class AuditVoucherTool(BaseTool):
    """审核凭证风险。"""

    class InputSchema(BaseModel):
        """审核工具入参。"""

        target: str = Field(..., description="必须为 latest、all 或 voucher_id")
        voucher_id: int | None = Field(default=None, description="当 target=voucher_id 时必填")

    name: str = "audit_voucher"
    description: str = "审核最新凭证、全部凭证或指定凭证的规则风险。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行审核工具。"""
        payload = self.InputSchema.model_validate(kwargs)
        router = FinanceDepartmentToolContextRegistry.get_context().audit_voucher_router
        response = router.route(
            {
                "target": payload.target,
                "voucher_id": payload.voucher_id,
            }
        )
        return response.to_tool_message_content()


audit_voucher_tool = AuditVoucherTool()
