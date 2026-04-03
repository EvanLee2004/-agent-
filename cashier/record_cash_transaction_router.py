"""记录资金收付工具入口。"""

from cashier.cashier_error import CashierError
from cashier.cashier_service import CashierService
from cashier.record_cash_transaction_command import RecordCashTransactionCommand
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse


class RecordCashTransactionRouter(ToolRouter):
    """记录资金收付工具入口。"""

    def __init__(self, cashier_service: CashierService):
        self._cashier_service = cashier_service

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行资金收付记录路由。"""
        try:
            transaction_id = self._cashier_service.record_transaction(
                RecordCashTransactionCommand(
                    transaction_date=str(arguments["transaction_date"]).strip(),
                    direction=str(arguments["direction"]).strip(),
                    amount=float(arguments["amount"]),
                    account_name=str(arguments["account_name"]).strip(),
                    summary=str(arguments["summary"]).strip(),
                    counterparty=str(arguments.get("counterparty", "")).strip(),
                    status=str(arguments.get("status", "completed")).strip() or "completed",
                    related_voucher_id=(
                        int(arguments["related_voucher_id"])
                        if arguments.get("related_voucher_id") not in {None, ""}
                        else None
                    ),
                )
            )
            return ToolRouterResponse(
                tool_name="record_cash_transaction",
                success=True,
                payload={"transaction_id": transaction_id},
            )
        except (CashierError, TypeError, ValueError) as error:
            return ToolRouterResponse(
                tool_name="record_cash_transaction",
                success=False,
                error_message=f"资金记录参数无效: {str(error)}",
            )

