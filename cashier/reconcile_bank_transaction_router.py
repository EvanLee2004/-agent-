"""银行流水对账工具路由。"""

from cashier.cashier_error import CashierError
from cashier.cashier_service import CashierService
from cashier.reconcile_bank_transaction_command import ReconcileBankTransactionCommand
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse


class ReconcileBankTransactionRouter(ToolRouter):
    """银行流水对账工具入口。"""

    def __init__(self, cashier_service: CashierService):
        self._cashier_service = cashier_service

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行银行流水对账。"""
        try:
            transaction = self._cashier_service.reconcile_transaction(
                ReconcileBankTransactionCommand(
                    transaction_id=int(arguments.get("transaction_id") or 0),
                    linked_voucher_id=(
                        int(arguments["linked_voucher_id"])
                        if arguments.get("linked_voucher_id") is not None
                        else None
                    ),
                )
            )
            return ToolRouterResponse(
                tool_name="reconcile_bank_transaction",
                success=True,
                payload={
                    "transaction_id": transaction.transaction_id,
                    "status": transaction.status,
                    "linked_voucher_id": transaction.linked_voucher_id,
                },
                voucher_ids=(
                    [transaction.linked_voucher_id]
                    if transaction.linked_voucher_id is not None
                    else []
                ),
                context_refs=[f"bank_transaction:{transaction.transaction_id}"],
            )
        except (CashierError, TypeError, ValueError) as error:
            return ToolRouterResponse(
                tool_name="reconcile_bank_transaction",
                success=False,
                error_message=f"银行流水对账无效: {str(error)}",
            )
