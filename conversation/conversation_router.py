"""会话入口。"""

import logging

from conversation.conversation_error import ConversationError
from conversation.conversation_request import ConversationRequest
from conversation.conversation_response import ConversationResponse
from conversation.conversation_service import ConversationService

logger = logging.getLogger(__name__)


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
            return ConversationResponse(reply_text="服务暂时不可用，请稍后重试。")
        except Exception:
            # 捕获所有异常以避免 Python traceback 暴露给用户。
            # DeerFlow 底层错误信息往往包含配置或第三方细节，直接回显会降低产品稳定感，
            # 也会扩大排障信息暴露面。将详细错误记录到日志供排查使用。
            logger.exception("会话处理异常")
            return ConversationResponse(reply_text="服务暂时不可用，请稍后重试。")
