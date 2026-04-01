"""审核工具入口。"""

from audit.audit_error import AuditError
from audit.audit_request import AuditRequest
from audit.audit_service import AuditService
from audit.audit_voucher_command import AuditVoucherCommand
from conversation.tool_definition import ToolDefinition
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse


AUDIT_VOUCHER_PARAMETERS = {
    "type": "object",
    "properties": {
        "target": {
            "type": "string",
            "enum": ["latest", "all", "voucher_id"],
        },
        "voucher_id": {
            "type": "integer",
            "description": "当 target=voucher_id 时必填",
        },
    },
    "required": ["target"],
}


def _serialize_flag(flag) -> dict:
    """序列化单条审核标记。"""
    return {
        "code": flag.code,
        "severity": flag.severity,
        "message": flag.message,
    }


def _build_success_payload(result) -> dict:
    """构造审核工具返回值。"""
    return {
        "audited_voucher_ids": result.audited_voucher_ids,
        "risk_level": result.risk_level,
        "summary": result.summary,
        "suggestion": result.suggestion,
        "flags": [_serialize_flag(flag) for flag in result.flags],
    }


class AuditVoucherRouter(ToolRouter):
    """审核工具入口。"""

    def __init__(self, audit_service: AuditService):
        self._audit_service = audit_service

    def get_definition(self) -> ToolDefinition:
        """返回工具定义。"""
        return ToolDefinition(
            name="audit_voucher",
            description="审核最新凭证、全部凭证或指定凭证的规则风险。",
            parameters=AUDIT_VOUCHER_PARAMETERS,
        )

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行审核工具调用。"""
        try:
            result = self._audit_service.audit_voucher(
                AuditVoucherCommand(audit_request=AuditRequest.from_dict(arguments))
            )
            return ToolRouterResponse(
                tool_name="audit_voucher",
                success=True,
                payload=_build_success_payload(result),
            )
        except AuditError as error:
            return ToolRouterResponse(
                tool_name="audit_voucher",
                success=False,
                error_message=f"审核参数无效: {str(error)}",
            )
