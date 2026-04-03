"""会话服务。"""

from conversation.conversation_error import ConversationError
from conversation.conversation_request import ConversationRequest
from conversation.conversation_response import ConversationResponse
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from department.department_error import DepartmentError
from department.finance_department_request import FinanceDepartmentRequest
from department.finance_department_service import FinanceDepartmentService


class ConversationService:
    """会话服务。"""

    def __init__(
        self,
        finance_department_service: FinanceDepartmentService,
        reply_text_sanitizer: ReplyTextSanitizer,
    ):
        self._finance_department_service = finance_department_service
        self._reply_text_sanitizer = reply_text_sanitizer

    def reply(self, request: ConversationRequest) -> ConversationResponse:
        """处理会话请求。

        Args:
            request: 外层会话请求。

        Returns:
            用户可见的会话响应。
        """
        try:
            department_response = self._finance_department_service.reply(
                FinanceDepartmentRequest(
                    user_input=request.user_input,
                    thread_id=request.thread_id,
                )
            )
        except DepartmentError as error:
            raise ConversationError(str(error)) from error
        return ConversationResponse(
            reply_text=self._reply_text_sanitizer.sanitize(department_response.reply_text),
            role_traces=department_response.role_traces,
        )
