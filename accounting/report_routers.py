"""账簿报表工具路由。"""

from accounting.accounting_service import AccountingService
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse


def _serialize_balance(row) -> dict:
    """序列化科目余额。"""
    return {
        "subject_code": row.subject_code,
        "subject_name": row.subject_name,
        "normal_balance": row.normal_balance,
        "debit_total": row.debit_total,
        "credit_total": row.credit_total,
        "balance_direction": row.balance_direction,
        "balance_amount": row.balance_amount,
    }


def _serialize_entry(row) -> dict:
    """序列化账簿明细。"""
    return {
        "voucher_id": row.voucher_id,
        "voucher_number": row.voucher_number,
        "voucher_date": row.voucher_date,
        "period_name": row.period_name,
        "subject_code": row.subject_code,
        "subject_name": row.subject_name,
        "debit_amount": row.debit_amount,
        "credit_amount": row.credit_amount,
        "summary": row.summary,
        "description": row.description,
    }


class QueryAccountBalanceRouter(ToolRouter):
    """科目余额查询工具入口。"""

    def __init__(self, accounting_service: AccountingService):
        self._accounting_service = accounting_service

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行科目余额查询。"""
        period_name = str(arguments.get("period_name") or "").strip() or None
        rows = self._accounting_service.list_account_balances(period_name)
        return ToolRouterResponse(
            tool_name="query_account_balance",
            success=True,
            payload={
                "period_name": period_name,
                "count": len(rows),
                "items": [_serialize_balance(row) for row in rows],
            },
        )


class QueryLedgerEntriesRouter(ToolRouter):
    """总账/明细账查询工具入口。"""

    def __init__(self, accounting_service: AccountingService):
        self._accounting_service = accounting_service

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行账簿明细查询。"""
        period_name = str(arguments.get("period_name") or "").strip() or None
        subject_code = str(arguments.get("subject_code") or "").strip() or None
        limit = int(arguments.get("limit") or 200)
        rows = self._accounting_service.list_ledger_entries(
            period_name=period_name,
            subject_code=subject_code,
            limit=limit,
        )
        return ToolRouterResponse(
            tool_name="query_ledger_entries",
            success=True,
            payload={
                "period_name": period_name,
                "subject_code": subject_code,
                "count": len(rows),
                "items": [_serialize_entry(row) for row in rows],
            },
        )


class QueryTrialBalanceRouter(ToolRouter):
    """试算平衡查询工具入口。"""

    def __init__(self, accounting_service: AccountingService):
        self._accounting_service = accounting_service

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行试算平衡查询。"""
        period_name = str(arguments.get("period_name") or "").strip() or None
        report = self._accounting_service.build_trial_balance(period_name)
        return ToolRouterResponse(
            tool_name="query_trial_balance",
            success=True,
            payload={
                "period_name": report.period_name,
                "debit_total": report.debit_total,
                "credit_total": report.credit_total,
                "difference": report.difference,
                "balanced": report.balanced,
                "items": [_serialize_balance(row) for row in report.rows],
            },
        )
