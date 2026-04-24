"""CLI 请求处理器。

负责 app 层的两项跨层关注点：
1. 请求级会计工具上下文作用域管理（open_context_scope）
2. 异常翻译为用户友好的中文文本（而非 HTTP 错误）

这使得 conversation/ 层保持纯净，不依赖 runtime/crewai/* 模块。
"""

import logging

from conversation.conversation_error import ConversationError
from conversation.conversation_request import ConversationRequest
from conversation.conversation_response import ConversationResponse
from conversation.conversation_router import ConversationRouter
from runtime.crewai.accounting_tool_context import AccountingToolContext
from runtime.crewai.accounting_tool_context_registry import (
    AccountingToolContextRegistry,
)

logger = logging.getLogger(__name__)


def _with_cli_scope(
    router: ConversationRouter,
    tool_context: AccountingToolContext,
    request: ConversationRequest,
) -> ConversationResponse:
    """在请求级作用域内调用 router，将异常翻译为用户友好文本。

    CliConversationHandler 专用。ConversationError 直接透传 str(e)，
    其他异常翻译为通用文案。

    错误翻译策略：
    - ConversationError：直接使用 str(e)（用户可理解的中文业务描述）
    - 其他未预期异常：通用友好文案，不暴露技术细节

    Args:
        router: 纯净的会话路由。
        tool_context: 会计工具上下文。
        request: 会话请求。

    Returns:
        用户可见的会话响应。
    """
    with AccountingToolContextRegistry.open_context_scope(tool_context):
        try:
            return router.handle(request)
        except ConversationError as e:
            # ConversationError 已经是用户可理解的中文业务错误描述
            #（如"凭证不存在"、"金额不合法"），直接透传给用户。
            return ConversationResponse(reply_text=str(e))
        except Exception:
            logger.exception("CLI 会话处理异常")
            return ConversationResponse(reply_text="服务暂时不可用，请稍后重试。")


class CliConversationHandler:
    """CLI 专用的请求处理器。

    职责：
    - 在 handle() 中打开请求级会计工具上下文作用域
    - 调用纯净的 ConversationRouter
    - 将异常翻译为用户友好的中文文本（而非 HTTP 错误）

    错误翻译策略：
    - ConversationError：直接使用 str(e)（用户可理解的中文业务描述）
    - 其他未预期异常：通用友好文案，不暴露技术细节
    """

    def __init__(
        self,
        router: ConversationRouter,
        tool_context: AccountingToolContext,
    ):
        """构造 CLI 请求处理器。

        Args:
            router: 纯净的会话路由（不包含作用域管理和错误翻译）。
            tool_context: 会计工具上下文（每个请求共享同一实例，
                通过 open_context_scope 实现请求级作用域）。
        """
        self._router = router
        self._tool_context = tool_context

    def handle(self, request: ConversationRequest) -> ConversationResponse:
        """处理会话请求（CLI 专用错误翻译）。

        打开请求级工具上下文作用域，在作用域内调用纯净的 router。
        异常翻译为用户友好的中文文案。

        Args:
            request: 会话请求。

        Returns:
            用户可见的会话响应（异常被翻译为友好文案）。
        """
        return _with_cli_scope(self._router, self._tool_context, request)
