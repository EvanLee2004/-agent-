"""API 请求处理器。

负责 app 层的两项跨层关注点：
1. 请求级工具上下文作用域管理（open_context_scope）
2. 异常翻译为 HTTP 错误（400/500）

这使得 conversation/ 层保持纯净，不依赖 runtime/deerflow/* 模块。
"""

import logging

from conversation.conversation_error import ConversationError
from conversation.conversation_request import ConversationRequest
from conversation.conversation_response import ConversationResponse
from conversation.conversation_router import ConversationRouter
from department.department_error import DepartmentError
from fastapi import HTTPException
from runtime.deerflow.finance_department_tool_context import FinanceDepartmentToolContext
from runtime.deerflow.finance_department_tool_context_registry import (
    FinanceDepartmentToolContextRegistry,
)

logger = logging.getLogger(__name__)


def _with_api_scope(
    router: ConversationRouter,
    tool_context: FinanceDepartmentToolContext,
    request: ConversationRequest,
) -> ConversationResponse:
    """在请求级作用域内调用 router，将异常翻译为 HTTP 400/500。

    AppConversationHandler 专用。捕获 ConversationError → HTTP 400，
    其他异常 → HTTP 500。不泄露 DeerFlow 底层细节。

    Args:
        router: 纯净的会话路由。
        tool_context: 财务工具上下文。
        request: 会话请求。

    Returns:
        ConversationResponse。

    Raises:
        HTTPException: 400 业务错误，或 500 内部错误。
    """
    with FinanceDepartmentToolContextRegistry.open_context_scope(tool_context):
        try:
            return router.handle(request)
        except ConversationError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except DepartmentError as e:
            logger.exception("DepartmentError 传播到 AppConversationHandler")
            raise HTTPException(status_code=500, detail="服务暂时不可用，请稍后重试。") from e
        except Exception as e:
            logger.exception("会话处理异常")
            raise HTTPException(status_code=500, detail="服务暂时不可用，请稍后重试。") from e


class AppConversationHandler:
    """API 专用的请求处理器。

    职责：
    - 在 handle() 中打开请求级工具上下文作用域
    - 调用纯净的 ConversationRouter
    - 将异常翻译为 HTTP 400/500（由 FastAPI 转换为标准错误响应）

    错误翻译策略：
    - ConversationError：HTTP 400，detail = str(e)（业务错误原文）
    - DepartmentError：HTTP 500（防御性处理）
    - 其他未预期异常：HTTP 500，detail = "服务暂时不可用，请稍后重试。"
    """

    def __init__(
        self,
        router: ConversationRouter,
        tool_context: FinanceDepartmentToolContext,
    ):
        """构造请求处理器。

        Args:
            router: 纯净的会话路由（不包含作用域管理和错误翻译）。
            tool_context: 财务工具上下文（每个请求共享同一实例，
                通过 open_context_scope 实现请求级作用域）。
        """
        self._router = router
        self._tool_context = tool_context

    def handle(self, request: ConversationRequest) -> ConversationResponse:
        """处理会话请求。

        打开请求级工具上下文作用域，在作用域内调用纯净的 router。
        异常翻译为 HTTP 400/500（供 FastAPI 层的 endpoint 使用）。

        Args:
            request: 会话请求。

        Returns:
            ConversationResponse。

        Raises:
            HTTPException: 400 如果是请求问题，500/503 如果是内部执行失败。
        """
        return _with_api_scope(self._router, self._tool_context, request)
