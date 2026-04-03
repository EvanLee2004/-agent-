"""记录资金收付 LangChain 工具。"""

from typing import Optional

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from department.finance_department_tool_context_registry import FinanceDepartmentToolContextRegistry


class RecordCashTransactionTool(BaseTool):
    """记录一条资金收付事实。"""

    class InputSchema(BaseModel):
        """记录资金收付工具入参。"""

        transaction_date: str = Field(..., description="收付日期，格式 YYYY-MM-DD")
        direction: str = Field(..., description="方向，必须为 receipt 或 payment")
        amount: float = Field(..., description="收付金额，必须大于 0")
        account_name: str = Field(..., description="发生收付的账户名称")
        summary: str = Field(..., description="资金摘要")
        counterparty: str = Field(default="", description="对方单位或个人，可选")
        status: str = Field(default="completed", description="资金状态，默认 completed")
        related_voucher_id: Optional[int] = Field(default=None, description="关联凭证主键，可选")

    name: str = "record_cash_transaction"
    description: str = "记录一条已经发生的资金收付事实，例如付款、收款、报销支付。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行记录资金收付工具。"""
        payload = self.InputSchema.model_validate(kwargs)
        router = FinanceDepartmentToolContextRegistry.get_context().record_cash_transaction_router
        response = router.route(payload.model_dump())
        return response.to_tool_message_content()


record_cash_transaction_tool = RecordCashTransactionTool()
