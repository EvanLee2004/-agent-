"""凭证生命周期工具路由。"""

from accounting.accounting_error import AccountingError
from accounting.accounting_service import AccountingService
from accounting.correct_voucher_command import CorrectVoucherCommand
from accounting.record_voucher_command import RecordVoucherCommand
from accounting.reverse_voucher_command import ReverseVoucherCommand
from accounting.voucher_draft import VoucherDraft
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse


def _serialize_voucher(voucher) -> dict:
    """序列化凭证生命周期响应。"""
    return {
        "voucher_id": voucher.voucher_id,
        "voucher_number": voucher.voucher_number,
        "period_name": voucher.period_name,
        "voucher_date": voucher.voucher_date,
        "summary": voucher.summary,
        "status": voucher.status,
        "source_voucher_id": voucher.source_voucher_id,
        "lifecycle_action": voucher.lifecycle_action,
        "posted_at": voucher.posted_at,
        "voided_at": voucher.voided_at,
    }


class PostVoucherRouter(ToolRouter):
    """凭证过账工具入口。"""

    def __init__(self, accounting_service: AccountingService):
        self._accounting_service = accounting_service

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行凭证过账。"""
        try:
            voucher = self._accounting_service.post_voucher(
                int(arguments.get("voucher_id") or 0)
            )
            return ToolRouterResponse(
                tool_name="post_voucher",
                success=True,
                payload=_serialize_voucher(voucher),
                voucher_ids=[voucher.voucher_id],
                context_refs=[f"voucher:{voucher.voucher_id}"],
            )
        except (AccountingError, TypeError, ValueError) as error:
            return ToolRouterResponse(
                tool_name="post_voucher",
                success=False,
                error_message=f"凭证过账失败: {str(error)}",
            )


class VoidVoucherRouter(ToolRouter):
    """凭证作废工具入口。"""

    def __init__(self, accounting_service: AccountingService):
        self._accounting_service = accounting_service

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行凭证作废。"""
        try:
            voucher = self._accounting_service.void_voucher(
                int(arguments.get("voucher_id") or 0)
            )
            return ToolRouterResponse(
                tool_name="void_voucher",
                success=True,
                payload=_serialize_voucher(voucher),
                voucher_ids=[voucher.voucher_id],
                context_refs=[f"voucher:{voucher.voucher_id}"],
            )
        except (AccountingError, TypeError, ValueError) as error:
            return ToolRouterResponse(
                tool_name="void_voucher",
                success=False,
                error_message=f"凭证作废失败: {str(error)}",
            )


class ReverseVoucherRouter(ToolRouter):
    """红冲凭证工具入口。"""

    def __init__(self, accounting_service: AccountingService):
        self._accounting_service = accounting_service

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行凭证红冲。"""
        try:
            voucher = self._accounting_service.reverse_voucher(
                ReverseVoucherCommand(
                    voucher_id=int(arguments.get("voucher_id") or 0),
                    reversal_date=str(arguments.get("reversal_date") or "").strip()
                    or None,
                )
            )
            return ToolRouterResponse(
                tool_name="reverse_voucher",
                success=True,
                payload=_serialize_voucher(voucher),
                voucher_ids=[voucher.voucher_id],
                context_refs=[
                    f"voucher:{voucher.voucher_id}",
                    f"voucher:{voucher.source_voucher_id}",
                ],
            )
        except (AccountingError, TypeError, ValueError) as error:
            return ToolRouterResponse(
                tool_name="reverse_voucher",
                success=False,
                error_message=f"凭证红冲失败: {str(error)}",
            )


class CorrectVoucherRouter(ToolRouter):
    """凭证更正工具入口。"""

    def __init__(self, accounting_service: AccountingService):
        self._accounting_service = accounting_service

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行凭证更正。"""
        try:
            replacement_document = arguments.get("replacement_voucher")
            if not isinstance(replacement_document, dict):
                raise AccountingError("replacement_voucher 必须是对象")
            reversal_id, replacement_id = self._accounting_service.correct_voucher(
                CorrectVoucherCommand(
                    voucher_id=int(arguments.get("voucher_id") or 0),
                    replacement_command=RecordVoucherCommand(
                        voucher_draft=VoucherDraft.from_dict(replacement_document)
                    ),
                    reversal_date=str(arguments.get("reversal_date") or "").strip()
                    or None,
                )
            )
            return ToolRouterResponse(
                tool_name="correct_voucher",
                success=True,
                payload={
                    "reversal_voucher_id": reversal_id,
                    "replacement_voucher_id": replacement_id,
                },
                voucher_ids=[reversal_id, replacement_id],
                context_refs=[f"voucher:{reversal_id}", f"voucher:{replacement_id}"],
            )
        except (AccountingError, TypeError, ValueError) as error:
            return ToolRouterResponse(
                tool_name="correct_voucher",
                success=False,
                error_message=f"凭证更正失败: {str(error)}",
            )
