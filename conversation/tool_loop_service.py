"""工具循环服务。"""

import re
from typing import Optional

from conversation.conversation_error import ConversationError
from conversation.tool_loop_request import ToolLoopRequest
from conversation.tool_loop_result import ToolLoopResult
from conversation.tool_router_catalog import ToolRouterCatalog
from conversation.tool_router_response import ToolRouterResponse
from conversation.tool_use_policy import ToolUsePolicy
from llm.llm_chat_repository import LlmChatRepository
from llm.llm_chat_request import LlmChatRequest
from llm.llm_message import LlmMessage


MAX_TOOL_LOOP_STEPS = 8
THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
MEMORY_RECALL_TOOL_NAME = "search_memory"


def _build_initial_messages(request: ToolLoopRequest) -> list[LlmMessage]:
    """构造工具循环的首轮消息。"""
    return [
        LlmMessage(role="system", content=request.system_prompt),
        LlmMessage(role="user", content=request.user_input),
    ]


def _resolve_tool_choice(step_index: int, force_required_tool_choice: bool) -> str:
    """确定当前轮是否必须调用工具。"""
    if step_index == 0 or force_required_tool_choice:
        return "required"
    return "auto"


def _sanitize_final_reply(content: str) -> str:
    """清理最终用户回复。"""
    cleaned_content = THINK_BLOCK_PATTERN.sub("", content)
    cleaned_content = re.sub(r"\n{3,}", "\n\n", cleaned_content)
    return cleaned_content.strip()


def _should_retry_memory_recall(
    is_memory_recall_request: bool,
    executed_tool_names: list[str],
    has_memory_recall_retry: bool,
) -> bool:
    """判断当前轮是否需要先纠偏再继续。"""
    return (
        is_memory_recall_request
        and MEMORY_RECALL_TOOL_NAME not in executed_tool_names
        and not has_memory_recall_retry
    )


def _should_reject_memory_recall(
    is_memory_recall_request: bool,
    executed_tool_names: list[str],
    has_memory_recall_retry: bool,
) -> bool:
    """判断记忆召回场景是否已经偏离到必须终止。"""
    return (
        is_memory_recall_request
        and MEMORY_RECALL_TOOL_NAME not in executed_tool_names
        and has_memory_recall_retry
    )


def _build_memory_recall_correction_message() -> str:
    """构造记忆召回纠偏消息。"""
    return (
        "当前用户问题要求你基于系统已保存的记忆来回答。"
        "你尚未调用 `search_memory`，因此不能直接判断“记住了什么”或“没有记忆”。"
        "请先调用 `search_memory` 查询，再给出最终中文答复。"
    )


class ToolLoopService:
    """工具循环服务。"""

    def __init__(
        self,
        llm_chat_repository: LlmChatRepository,
        tool_router_catalog: ToolRouterCatalog,
        tool_use_policy: ToolUsePolicy,
    ):
        self._llm_chat_repository = llm_chat_repository
        self._tool_router_catalog = tool_router_catalog
        self._tool_use_policy = tool_use_policy

    def run_tool_loop(self, request: ToolLoopRequest) -> ToolLoopResult:
        """执行原生 function calling 主循环。"""
        messages = _build_initial_messages(request)
        return self._run_steps(
            request.user_input,
            messages,
            [],
            [],
        )

    def _run_steps(
        self,
        user_input: str,
        messages: list[LlmMessage],
        executed_tool_names: list[str],
        tool_router_responses: list[ToolRouterResponse],
    ) -> ToolLoopResult:
        """执行工具循环的各轮处理。"""
        is_memory_recall_request = self._tool_use_policy.is_memory_recall_request(user_input)
        has_memory_recall_retry = False
        force_required_tool_choice = False
        for step_index in range(MAX_TOOL_LOOP_STEPS):
            llm_response = self._run_single_step(
                messages,
                step_index,
                force_required_tool_choice,
                executed_tool_names,
                tool_router_responses,
            )
            force_required_tool_choice = False
            if llm_response is None:
                continue
            if self._handle_memory_recall_guard(
                messages,
                is_memory_recall_request,
                executed_tool_names,
                has_memory_recall_retry,
            ):
                has_memory_recall_retry = True
                force_required_tool_choice = True
                continue
            return self._build_final_result(llm_response.content, executed_tool_names, tool_router_responses)
        raise ConversationError("工具调用轮次超限，请检查 prompt 或工具设计")

    def _run_single_step(
        self,
        messages: list[LlmMessage],
        step_index: int,
        force_required_tool_choice: bool,
        executed_tool_names: list[str],
        tool_router_responses: list[ToolRouterResponse],
    ) -> Optional[object]:
        """执行单轮请求并处理工具调用。"""
        llm_response = self._request_llm_response(
            messages=messages,
            step_index=step_index,
            force_required_tool_choice=force_required_tool_choice,
        )
        self._append_assistant_message(messages, llm_response.assistant_message)
        if self._handle_tool_call_round(
            messages=messages,
            llm_response=llm_response,
            executed_tool_names=executed_tool_names,
            tool_router_responses=tool_router_responses,
        ):
            return None
        return llm_response

    def _handle_memory_recall_guard(
        self,
        messages: list[LlmMessage],
        is_memory_recall_request: bool,
        executed_tool_names: list[str],
        has_memory_recall_retry: bool,
    ) -> bool:
        """在记忆召回场景下执行软纠偏。"""
        if _should_retry_memory_recall(
            is_memory_recall_request=is_memory_recall_request,
            executed_tool_names=executed_tool_names,
            has_memory_recall_retry=has_memory_recall_retry,
        ):
            self._append_memory_recall_correction(messages)
            return True
        if _should_reject_memory_recall(
            is_memory_recall_request=is_memory_recall_request,
            executed_tool_names=executed_tool_names,
            has_memory_recall_retry=has_memory_recall_retry,
        ):
            raise ConversationError("记忆召回场景必须先查询记忆源")
        return False

    def _request_llm_response(
        self,
        messages: list[LlmMessage],
        step_index: int,
        force_required_tool_choice: bool,
    ):
        """向模型发起单轮请求。"""
        llm_response = self._llm_chat_repository.send_chat_request(
            LlmChatRequest(
                messages=messages,
                tools=self._tool_router_catalog.list_tool_definitions(),
                tool_choice=_resolve_tool_choice(step_index, force_required_tool_choice),
            )
        )
        if not llm_response.success:
            raise ConversationError(llm_response.error_message or "工具调用失败")
        return llm_response

    def _append_assistant_message(
        self,
        messages: list[LlmMessage],
        assistant_message: Optional[LlmMessage],
    ) -> None:
        """把 assistant 消息追加到对话历史。"""
        if assistant_message is not None:
            messages.append(assistant_message)

    def _handle_tool_call_round(
        self,
        messages: list[LlmMessage],
        llm_response,
        executed_tool_names: list[str],
        tool_router_responses: list[ToolRouterResponse],
    ) -> bool:
        """处理一轮工具调用结果。"""
        if not llm_response.tool_calls:
            return False
        self._append_tool_messages(
            messages,
            executed_tool_names,
            tool_router_responses,
            self._route_tool_calls(llm_response.tool_calls),
        )
        return True

    def _append_tool_messages(
        self,
        messages: list[LlmMessage],
        executed_tool_names: list[str],
        tool_router_responses: list[ToolRouterResponse],
        routed_responses: list[tuple[ToolRouterResponse, object]],
    ) -> None:
        """把工具执行结果追加到对话历史。"""
        for routed_response, tool_call in routed_responses:
            executed_tool_names.append(routed_response.tool_name)
            tool_router_responses.append(routed_response)
            messages.append(
                LlmMessage(
                    role="tool",
                    content=routed_response.to_tool_message_content(),
                    tool_call_id=tool_call.call_id,
                )
            )

    def _append_memory_recall_correction(self, messages: list[LlmMessage]) -> None:
        """在记忆召回场景下追加纠偏约束。"""
        messages.append(
            LlmMessage(
                role="system",
                content=_build_memory_recall_correction_message(),
            )
        )

    def _route_tool_calls(self, tool_calls: list) -> list[tuple[ToolRouterResponse, object]]:
        """分发工具调用。"""
        routed_responses = []
        for tool_call in tool_calls:
            tool_router = self._tool_router_catalog.get_tool_router(tool_call.tool_name)
            if tool_router is None:
                raise ConversationError(f"未注册工具: {tool_call.tool_name}")
            routed_responses.append((tool_router.route(tool_call.arguments), tool_call))
        return routed_responses

    def _build_final_result(
        self,
        content: str,
        executed_tool_names: list[str],
        tool_router_responses: list[ToolRouterResponse],
    ) -> ToolLoopResult:
        """构造最终工具循环结果。"""
        if not executed_tool_names:
            raise ConversationError("模型未调用任何工具，主流程拒绝退回自由聊天")
        final_reply = _sanitize_final_reply(content)
        if not final_reply:
            raise ConversationError("模型未生成最终回复")
        return ToolLoopResult(
            final_reply=final_reply,
            executed_tool_names=executed_tool_names,
            tool_router_responses=tool_router_responses,
        )
