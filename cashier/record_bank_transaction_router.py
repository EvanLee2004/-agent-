"""记录银行流水工具路由。"""

from cashier.cashier_error import CashierError
from cashier.cashier_service import CashierService
from cashier.record_bank_transaction_command import RecordBankTransactionCommand
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse


class RecordBankTransactionRouter(ToolRouter):
    """记录银行流水工具入口。"""

    def __init__(self, cashier_service: CashierService):
        self._cashier_service = cashier_service

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行银行流水记录。"""
        try:
            command = RecordBankTransactionCommand(
                transaction_date=str(arguments.get("transaction_date") or "").strip(),
                direction=str(arguments.get("direction") or "").strip(),
                amount=float(arguments.get("amount") or 0),
                account_name=str(arguments.get("account_name") or "").strip(),
                counterparty=str(arguments.get("counterparty") or "").strip(),
                summary=str(arguments.get("summary") or "").strip(),
            )
            transaction_id = self._cashier_service.record_transaction(command)
            return ToolRouterResponse(
                tool_name="record_bank_transaction",
                success=True,
                payload={
                    "transaction_id": transaction_id,
                    "transaction_date": command.transaction_date,
                    "direction": command.direction,
                    "amount": command.amount,
                    "account_name": command.account_name,
                    "counterparty": command.counterparty,
                    "summary": command.summary,
                    "status": "unreconciled",
                },
                context_refs=[f"bank_transaction:{transaction_id}"],
            )
        except (CashierError, TypeError, ValueError) as error:
            return ToolRouterResponse(
                tool_name="record_bank_transaction",
                success=False,
                error_message=f"银行流水参数无效: {str(error)}",
            )
