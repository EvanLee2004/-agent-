"""解除银行流水对账工具路由。"""

from cashier.cashier_error import CashierError
from cashier.cashier_service import CashierService
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse


class UnreconcileBankTransactionRouter(ToolRouter):
    """解除银行流水对账工具入口。"""

    def __init__(self, cashier_service: CashierService):
        self._cashier_service = cashier_service

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行解除对账。"""
        try:
            transaction = self._cashier_service.unreconcile_transaction(
                int(arguments.get("transaction_id") or 0)
            )
            return ToolRouterResponse(
                tool_name="unreconcile_bank_transaction",
                success=True,
                payload={
                    "transaction_id": transaction.transaction_id,
                    "status": transaction.status,
                    "linked_voucher_id": transaction.linked_voucher_id,
                },
                context_refs=[f"bank_transaction:{transaction.transaction_id}"],
            )
        except (CashierError, TypeError, ValueError) as error:
            return ToolRouterResponse(
                tool_name="unreconcile_bank_transaction",
                success=False,
                error_message=f"银行流水解除对账失败: {str(error)}",
            )
