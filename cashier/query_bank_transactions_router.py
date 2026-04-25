"""查询银行流水工具路由。"""

from cashier.cashier_error import CashierError
from cashier.cashier_service import CashierService
from cashier.query_bank_transactions_query import QueryBankTransactionsQuery
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse


def _serialize_transaction(transaction) -> dict:
    """序列化银行流水。"""
    return {
        "transaction_id": transaction.transaction_id,
        "transaction_date": transaction.transaction_date,
        "direction": transaction.direction,
        "amount": transaction.amount,
        "account_name": transaction.account_name,
        "counterparty": transaction.counterparty,
        "summary": transaction.summary,
        "status": transaction.status,
        "linked_voucher_id": transaction.linked_voucher_id,
    }


class QueryBankTransactionsRouter(ToolRouter):
    """查询银行流水工具入口。"""

    def __init__(self, cashier_service: CashierService):
        self._cashier_service = cashier_service

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行银行流水查询。"""
        try:
            query = QueryBankTransactionsQuery(
                date_prefix=str(arguments.get("date") or "").strip() or None,
                status=str(arguments.get("status") or "").strip() or None,
                direction=str(arguments.get("direction") or "").strip() or None,
                limit=int(arguments.get("limit") or 20),
            )
            transactions = self._cashier_service.query_transactions(query)
            return ToolRouterResponse(
                tool_name="query_bank_transactions",
                success=True,
                payload={
                    "count": len(transactions),
                    "items": [_serialize_transaction(item) for item in transactions],
                },
                context_refs=[
                    f"bank_transaction:{item.transaction_id}"
                    for item in transactions
                ],
            )
        except (CashierError, TypeError, ValueError) as error:
            return ToolRouterResponse(
                tool_name="query_bank_transactions",
                success=False,
                error_message=f"银行流水查询参数无效: {str(error)}",
            )
