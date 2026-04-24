"""会话服务。

纯业务编排层，不包含任何运行时实现细节。
只负责：请求转发 → 业务编排 → 响应清洗。
"""

from conversation.conversation_error import ConversationError
from conversation.conversation_request import ConversationRequest
from conversation.conversation_response import ConversationResponse
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from department.accounting_department_request import AccountingDepartmentRequest
from department.accounting_department_service import AccountingDepartmentService
from department.department_error import DepartmentError


class ConversationService:
    """会话服务（纯业务编排层）。

    负责：
    - 业务编排层转发
    - 响应清洗

    注意：本服务不依赖 runtime/crewai/* 模块，保持业务编排层纯净。
    请求级工具上下文作用域和错误翻译由调用方的 app 层组件负责。
    """

    def __init__(
        self,
        accounting_department_service: AccountingDepartmentService,
        reply_text_sanitizer: ReplyTextSanitizer,
    ):
        """构造会话服务。

        Args:
            accounting_department_service: 会计部门主服务。
            reply_text_sanitizer: 回复文本清洗器。
        """
        self._accounting_department_service = accounting_department_service
        self._reply_text_sanitizer = reply_text_sanitizer

    def reply(self, request: ConversationRequest) -> ConversationResponse:
        """处理会话请求。

        Args:
            request: 外层会话请求。

        Returns:
            用户可见的会话响应。
        """
        try:
            department_response = self._accounting_department_service.reply(
                AccountingDepartmentRequest(
                    user_input=request.user_input,
                    thread_id=request.thread_id,
                )
            )
        except DepartmentError as error:
            raise ConversationError(str(error)) from error
        return ConversationResponse(
            reply_text=self._reply_text_sanitizer.sanitize(department_response.reply_text),
            collaboration_steps=department_response.collaboration_steps,
        )
