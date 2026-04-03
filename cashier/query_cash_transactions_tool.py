"""查询资金收付 LangChain 工具。"""

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from department.finance_department_tool_context_registry import FinanceDepartmentToolContextRegistry


class QueryCashTransactionsTool(BaseTool):
    """查询资金收付事实。"""

    class InputSchema(BaseModel):
        """查询资金收付工具入参。"""

        date: str = Field(default="", description="日期前缀，可选")
        direction: str = Field(default="", description="方向过滤，可选")
        limit: int = Field(default=20, description="最多返回条数")

    name: str = "query_cash_transactions"
    description: str = "查询已经记录的收款、付款和报销支付事实。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行资金收付查询工具。"""
        payload = self.InputSchema.model_validate(kwargs)
        router = FinanceDepartmentToolContextRegistry.get_context().query_cash_transactions_router
        response = router.route(payload.model_dump())
        return response.to_tool_message_content()


query_cash_transactions_tool = QueryCashTransactionsTool()
