"""税务工具入口。"""

from conversation.tool_definition import ToolDefinition
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse
from tax.calculate_tax_command import CalculateTaxCommand
from tax.tax_error import TaxError
from tax.tax_request import TaxRequest
from tax.tax_service import TaxService


CALCULATE_TAX_PARAMETERS = {
    "type": "object",
    "properties": {
        "tax_type": {
            "type": "string",
            "enum": ["vat", "corporate_income_tax"],
            "description": "必须严格使用 vat 或 corporate_income_tax",
        },
        "taxpayer_type": {
            "type": "string",
            "enum": ["small_scale_vat_taxpayer", "small_low_profit_enterprise"],
            "description": "必须严格使用 small_scale_vat_taxpayer 或 small_low_profit_enterprise",
        },
        "amount": {"type": "number"},
        "includes_tax": {
            "type": "boolean",
            "description": "仅当用户明确说“含税”或“价税合计”时填 true；否则默认 false",
        },
        "description": {"type": "string"},
    },
    "required": ["tax_type", "taxpayer_type", "amount", "includes_tax"],
}


def _build_success_payload(result) -> dict:
    """构造税务工具返回值。"""
    return {
        "tax_type": result.tax_type.value,
        "taxpayer_type": result.taxpayer_type.value,
        "taxable_base": result.taxable_base,
        "tax_rate": result.tax_rate,
        "payable_tax": result.payable_tax,
        "formula": result.formula,
        "policy_basis": result.policy_basis,
        "notes": result.notes,
    }


class CalculateTaxRouter(ToolRouter):
    """税务工具入口。"""

    def __init__(self, tax_service: TaxService):
        self._tax_service = tax_service

    def get_definition(self) -> ToolDefinition:
        """返回工具定义。"""
        return ToolDefinition(
            name="calculate_tax",
            description="按中国小企业基础税规则计算税额。",
            parameters=CALCULATE_TAX_PARAMETERS,
        )

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行税务工具调用。"""
        try:
            result = self._tax_service.calculate_tax(
                CalculateTaxCommand(tax_request=TaxRequest.from_dict(arguments))
            )
            return ToolRouterResponse(
                tool_name="calculate_tax",
                success=True,
                payload=_build_success_payload(result),
            )
        except TaxError as error:
            return ToolRouterResponse(
                tool_name="calculate_tax",
                success=False,
                error_message=f"税务参数无效: {str(error)}",
            )
