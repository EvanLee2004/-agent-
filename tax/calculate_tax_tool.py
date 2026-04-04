"""税务测算 LangChain 工具。"""

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from runtime.deerflow.finance_department_tool_context_registry import FinanceDepartmentToolContextRegistry


class CalculateTaxTool(BaseTool):
    """根据结构化税务参数执行税额测算。"""

    class InputSchema(BaseModel):
        """税务工具入参。"""

        tax_type: str = Field(..., description="必须严格使用 vat 或 corporate_income_tax")
        taxpayer_type: str = Field(
            ...,
            description="必须严格使用 small_scale_vat_taxpayer 或 small_low_profit_enterprise",
        )
        amount: float = Field(..., description="计税金额")
        includes_tax: bool = Field(
            ...,
            description="仅当用户明确说\"含税\"或\"价税合计\"时填 true；否则默认 false",
        )
        cost: float = Field(
            default=0.0,
            description="成本费用（仅企业所得税用），如收入100万成本60万则填600000",
        )
        description: str = Field(default="", description="业务场景说明，可选")

    name: str = "calculate_tax"
    description: str = "按中国小企业基础税规则计算税额。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行税务工具。"""
        payload = self.InputSchema.model_validate(kwargs)
        router = FinanceDepartmentToolContextRegistry.get_context().calculate_tax_router
        response = router.route(
            {
                "tax_type": payload.tax_type,
                "taxpayer_type": payload.taxpayer_type,
                "amount": payload.amount,
                "includes_tax": payload.includes_tax,
                "cost": payload.cost,
                "description": payload.description,
            }
        )
        return response.to_tool_message_content()


calculate_tax_tool = CalculateTaxTool()
