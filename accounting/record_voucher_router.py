"""记账工具入口。"""

from conversation.tool_definition import ToolDefinition
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse
from accounting.accounting_error import AccountingError
from accounting.accounting_service import AccountingService
from accounting.record_voucher_command import RecordVoucherCommand
from accounting.voucher_draft import VoucherDraft


RECORD_VOUCHER_PARAMETERS = {
    "type": "object",
    "properties": {
        "voucher_date": {"type": "string", "description": "凭证日期，格式 YYYY-MM-DD"},
        "summary": {"type": "string", "description": "业务摘要，要求简洁且能表达业务实质"},
        "source_text": {"type": "string", "description": "原始业务描述，可选"},
        "lines": {
            "type": "array",
            "description": "分录行，至少两条，且借贷平衡",
            "items": {
                "type": "object",
                "properties": {
                    "subject_code": {"type": "string"},
                    "subject_name": {"type": "string"},
                    "debit_amount": {"type": "number"},
                    "credit_amount": {"type": "number"},
                    "description": {"type": "string"},
                },
                "required": [
                    "subject_code",
                    "subject_name",
                    "debit_amount",
                    "credit_amount",
                    "description",
                ],
            },
        },
    },
    "required": ["voucher_date", "summary", "lines"],
}


def _build_success_payload(voucher_draft: VoucherDraft, voucher_id: int) -> dict:
    """构造记账成功的工具返回值。"""
    return {
        "voucher_id": voucher_id,
        "voucher_date": voucher_draft.voucher_date,
        "summary": voucher_draft.summary,
        "total_amount": voucher_draft.get_total_amount(),
        "anomaly_flag": voucher_draft.anomaly_flag,
        "anomaly_reason": voucher_draft.anomaly_reason,
        "lines": [
            {
                "subject_code": line.subject_code,
                "subject_name": line.subject_name,
                "debit_amount": line.debit_amount,
                "credit_amount": line.credit_amount,
                "description": line.description,
            }
            for line in voucher_draft.lines
        ],
    }


def _build_record_command(arguments: dict) -> RecordVoucherCommand:
    """把工具参数转换为记账命令。"""
    return RecordVoucherCommand(voucher_draft=VoucherDraft.from_dict(arguments))


class RecordVoucherRouter(ToolRouter):
    """记账工具入口。"""

    def __init__(self, accounting_service: AccountingService):
        self._accounting_service = accounting_service

    def get_definition(self) -> ToolDefinition:
        """返回工具定义。"""
        return ToolDefinition(
            name="record_voucher",
            description="把用户描述的业务交易记录为标准会计凭证，并落入主账数据库。",
            parameters=RECORD_VOUCHER_PARAMETERS,
        )

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行记账工具路由。

        Args:
            arguments: 工具参数。

        Returns:
            统一的工具路由响应。
        """
        try:
            command = _build_record_command(arguments)
            voucher_draft = command.voucher_draft
            voucher_id = self._accounting_service.record_voucher(command)
            return ToolRouterResponse(
                tool_name="record_voucher",
                success=True,
                payload=_build_success_payload(voucher_draft, voucher_id),
            )
        except AccountingError as error:
            return ToolRouterResponse(
                tool_name="record_voucher",
                success=False,
                error_message=f"记账参数无效: {str(error)}",
            )
