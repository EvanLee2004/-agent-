"""银行流水入账建议工具路由。"""

from cashier.cashier_error import CashierError
from cashier.cashier_service import CashierService
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse


class VoucherSuggestionRouter(ToolRouter):
    """根据银行流水生成凭证建议。"""

    def __init__(self, cashier_service: CashierService):
        self._cashier_service = cashier_service

    def route(self, arguments: dict) -> ToolRouterResponse:
        """生成凭证建议，不写入总账。"""
        try:
            transaction_id = int(arguments.get("transaction_id") or 0)
            suggestion = self._cashier_service.build_voucher_suggestion(transaction_id)
            return ToolRouterResponse(
                tool_name="suggest_voucher_from_bank_transaction",
                success=True,
                payload={
                    "transaction_id": transaction_id,
                    "suggested_voucher": suggestion,
                },
                context_refs=[f"bank_transaction:{transaction_id}"],
            )
        except (CashierError, TypeError, ValueError) as error:
            return ToolRouterResponse(
                tool_name="suggest_voucher_from_bank_transaction",
                success=False,
                error_message=f"银行流水入账建议失败: {str(error)}",
            )
