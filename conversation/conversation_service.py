"""会话服务。"""

from conversation.conversation_request import ConversationRequest
from conversation.conversation_response import ConversationResponse
from conversation.prompt_context_service import PromptContextService
from conversation.tool_loop_request import ToolLoopRequest
from conversation.tool_loop_service import ToolLoopService


class ConversationService:
    """会话服务。"""

    def __init__(
        self,
        prompt_context_service: PromptContextService,
        tool_loop_service: ToolLoopService,
    ):
        self._prompt_context_service = prompt_context_service
        self._tool_loop_service = tool_loop_service

    def reply(self, request: ConversationRequest) -> ConversationResponse:
        """处理会话请求。"""
        tool_loop_result = self._tool_loop_service.run_tool_loop(
            ToolLoopRequest(
                user_input=request.user_input,
                system_prompt=self._prompt_context_service.build_system_prompt(request.user_input),
            )
        )
        return ConversationResponse(
            reply_text=tool_loop_result.final_reply,
            executed_tool_names=tool_loop_result.executed_tool_names,
        )
