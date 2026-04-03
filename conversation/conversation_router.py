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
        except ConversationError:
            # 这里不把底层运行时细节直接暴露给最终用户。
            # 当前系统正在切向 DeerFlow 底层，错误信息往往包含配置或第三方细节，
            # 直接回显会降低产品稳定感，也会扩大排障信息暴露面。
            return ConversationResponse(reply_text="服务暂时不可用，请稍后重试。")
