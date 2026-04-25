"""查账工具入口。"""

from accounting.accounting_service import AccountingService
from accounting.query_vouchers_query import QueryVouchersQuery
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse


DEFAULT_QUERY_LIMIT = 20


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
        "period_name": voucher.period_name,
        "voucher_sequence": voucher.voucher_sequence,
        "voucher_date": voucher.voucher_date,
        "summary": voucher.summary,
        "total_amount": voucher.get_total_amount(),
        "status": voucher.status,
        "recorded_by": voucher.recorded_by,
        "source_voucher_id": voucher.source_voucher_id,
        "lifecycle_action": voucher.lifecycle_action,
        "posted_at": voucher.posted_at,
        "voided_at": voucher.voided_at,
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

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行查账路由。"""
        query = _build_query(arguments)
        vouchers = self._accounting_service.query_vouchers(query)
        return ToolRouterResponse(
            tool_name="query_vouchers",
            success=True,
            payload=_build_payload(vouchers),
            voucher_ids=[voucher.voucher_id for voucher in vouchers],
            context_refs=[f"voucher:{voucher.voucher_id}" for voucher in vouchers],
        )
