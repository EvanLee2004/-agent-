"""记账 LangChain 工具。"""

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from runtime.deerflow.finance_department_tool_context_registry import FinanceDepartmentToolContextRegistry


class RecordVoucherTool(BaseTool):
    """把自然语言业务转换后的凭证参数落入主账。"""

    class InputSchema(BaseModel):
        """记账工具入参。"""

        voucher_date: str = Field(..., description="凭证日期，格式 YYYY-MM-DD")
        summary: str = Field(..., description="业务摘要，要求简洁且能表达业务实质")
        source_text: str = Field(default="", description="原始业务描述，可选")
        lines: list[dict] = Field(
            ...,
            description="分录行，至少两条，且借贷平衡",
        )

    name: str = "record_voucher"
    description: str = "把用户描述的业务交易记录为标准会计凭证，并落入主账数据库。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行记账工具。

        Args:
            **kwargs: DeerFlow/ LangChain 透传的结构化参数。

        Returns:
            统一格式的工具响应 JSON 字符串。
        """
        payload = self.InputSchema.model_validate(kwargs)
        router = FinanceDepartmentToolContextRegistry.get_context().record_voucher_router
        response = router.route(
            {
                "voucher_date": payload.voucher_date,
                "summary": payload.summary,
                "source_text": payload.source_text,
                "lines": payload.lines,
            }
        )
        return response.to_tool_message_content()


record_voucher_tool = RecordVoucherTool()
