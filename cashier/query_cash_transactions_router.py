"""查询资金收付工具入口。"""

from cashier.cashier_service import CashierService
from cashier.query_cash_transactions_query import QueryCashTransactionsQuery
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse


class QueryCashTransactionsRouter(ToolRouter):
    """查询资金收付工具入口。"""

    def __init__(self, cashier_service: CashierService):
        self._cashier_service = cashier_service

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行资金收付查询路由。"""
        transactions = self._cashier_service.query_transactions(
            QueryCashTransactionsQuery(
                date_prefix=str(arguments.get("date", "")).strip() or None,
                direction=str(arguments.get("direction", "")).strip() or None,
                limit=int(arguments.get("limit", 20) or 20),
            )
        )
        return ToolRouterResponse(
            tool_name="query_cash_transactions",
            success=True,
            payload={
                "count": len(transactions),
                "items": [
                    {
                        "transaction_id": transaction.transaction_id,
                        "transaction_date": transaction.transaction_date,
                        "direction": transaction.direction,
                        "amount": transaction.amount,
                        "account_name": transaction.account_name,
                        "summary": transaction.summary,
                        "counterparty": transaction.counterparty,
                        "status": transaction.status,
                        "related_voucher_id": transaction.related_voucher_id,
                    }
                    for transaction in transactions
                ],
            },
        )

