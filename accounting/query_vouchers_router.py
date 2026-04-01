"""查账工具入口。"""

from accounting.accounting_service import AccountingService
from accounting.query_vouchers_query import QueryVouchersQuery
from conversation.tool_definition import ToolDefinition
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse


DEFAULT_QUERY_LIMIT = 20
QUERY_VOUCHERS_PARAMETERS = {
    "type": "object",
    "properties": {
        "date": {
            "type": "string",
            "description": "可选日期过滤，例如 2024-03 或 2024-03-01",
        },
        "status": {
            "type": "string",
            "description": "可选状态过滤，例如 pending 或 approved",
        },
        "limit": {
            "type": "integer",
            "description": "最大返回条数，默认 20",
        },
    },
}


def _build_query(arguments: dict) -> QueryVouchersQuery:
    """把工具参数转换为查账查询对象。"""
    return QueryVouchersQuery(
        date_prefix=str(arguments.get("date", "")).strip() or None,
        status=str(arguments.get("status", "")).strip() or None,
        limit=int(arguments.get("limit", DEFAULT_QUERY_LIMIT) or DEFAULT_QUERY_LIMIT),
    )


def _serialize_line(line) -> dict:
    """序列化凭证明细行。"""
    return {
        "subject_code": line.subject_code,
        "subject_name": line.subject_name,
        "debit_amount": line.debit_amount,
        "credit_amount": line.credit_amount,
        "description": line.description,
    }


def _serialize_voucher(voucher) -> dict:
    """序列化单张凭证。"""
    return {
        "voucher_id": voucher.voucher_id,
        "voucher_number": voucher.voucher_number,
        "voucher_date": voucher.voucher_date,
        "summary": voucher.summary,
        "total_amount": voucher.get_total_amount(),
        "status": voucher.status,
        "recorded_by": voucher.recorded_by,
        "lines": [_serialize_line(line) for line in voucher.lines],
    }


def _build_payload(vouchers: list) -> dict:
    """构造查账工具返回值。"""
    return {
        "count": len(vouchers),
        "items": [_serialize_voucher(voucher) for voucher in vouchers],
    }


class QueryVouchersRouter(ToolRouter):
    """查账工具入口。"""

    def __init__(self, accounting_service: AccountingService):
        self._accounting_service = accounting_service

    def get_definition(self) -> ToolDefinition:
        """返回工具定义。"""
        return ToolDefinition(
            name="query_vouchers",
            description="查询已入账的凭证列表，可按日期和状态过滤。",
            parameters=QUERY_VOUCHERS_PARAMETERS,
        )

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行查账路由。"""
        query = _build_query(arguments)
        vouchers = self._accounting_service.query_vouchers(query)
        return ToolRouterResponse(
            tool_name="query_vouchers",
            success=True,
            payload=_build_payload(vouchers),
        )
