"""会话服务。"""

from conversation.agent_runtime_repository import AgentRuntimeRepository
from conversation.agent_runtime_request import AgentRuntimeRequest
from conversation.conversation_request import ConversationRequest
from conversation.conversation_response import ConversationResponse
from conversation.reply_text_sanitizer import ReplyTextSanitizer


class ConversationService:
    """会话服务。"""

    def __init__(
        self,
        agent_runtime_repository: AgentRuntimeRepository,
        reply_text_sanitizer: ReplyTextSanitizer,
    ):
        self._agent_runtime_repository = agent_runtime_repository
        self._reply_text_sanitizer = reply_text_sanitizer

    def reply(self, request: ConversationRequest) -> ConversationResponse:
        """处理会话请求。

        Args:
            request: 外层会话请求。

        Returns:
            用户可见的会话响应。
        """
        runtime_response = self._agent_runtime_repository.reply(
            AgentRuntimeRequest(
                user_input=request.user_input,
                thread_id=request.thread_id,
            )
        )
        return ConversationResponse(
            reply_text=self._reply_text_sanitizer.sanitize(runtime_response.reply_text),
            executed_tool_names=runtime_response.executed_tool_names,
        )
