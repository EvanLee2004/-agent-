"""会话入口。

纯业务编排层，不包含任何运行时实现细节或异常处理。
负责将请求转发给 ConversationService 并返回其响应。
异常翻译和请求级作用域管理由调用方（app 层组件）负责。
"""

from conversation.conversation_request import ConversationRequest
from conversation.conversation_response import ConversationResponse
from conversation.conversation_service import ConversationService


class ConversationRouter:
    """会话入口（纯业务编排层）。

    职责：
    - 请求转发（ConversationRequest → ConversationService → ConversationResponse）
    - 不负责异常处理、作用域管理或错误翻译

    注意：本类不依赖 runtime/crewai/* 模块，保持业务编排层纯净。
    请求级工具上下文作用域和异常翻译由调用方的 app 层组件负责。
    """

    def __init__(self, conversation_service: ConversationService):
        """构造会话入口。

        Args:
            conversation_service: 业务编排层服务（纯会话逻辑）。
        """
        self._conversation_service = conversation_service

    def handle(self, request: ConversationRequest) -> ConversationResponse:
        """处理用户输入（纯转发）。

        异常不做捕获，直接传播给调用方（app 层组件）处理。

        Args:
            request: 会话请求。

        Returns:
            用户可见的会话响应。
        """
        return self._conversation_service.reply(request)
