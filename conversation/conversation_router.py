"""会话入口。"""

from conversation.conversation_error import ConversationError
from conversation.conversation_request import ConversationRequest
from conversation.conversation_response import ConversationResponse
from conversation.conversation_service import ConversationService


class ConversationRouter:
    """会话入口。"""

    def __init__(self, conversation_service: ConversationService):
        self._conversation_service = conversation_service

    def handle(self, request: ConversationRequest) -> ConversationResponse:
        """处理用户输入。

        Args:
            request: 会话请求。

        Returns:
            用户可见的会话响应。
        """
        try:
            return self._conversation_service.reply(request)
        except ConversationError as error:
            return ConversationResponse(reply_text=f"服务暂时不可用，请稍后重试。({str(error)})")
