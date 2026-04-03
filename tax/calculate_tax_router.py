"""税务工具入口。"""

from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse
from tax.calculate_tax_command import CalculateTaxCommand
from tax.tax_error import TaxError
from tax.tax_request import TaxRequest
from tax.tax_service import TaxService


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
