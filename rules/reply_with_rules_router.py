"""规则工具入口。"""

from conversation.tool_definition import ToolDefinition
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse
from conversation.tool_use_policy import ToolUsePolicy
from memory.memory_context_query import MemoryContextQuery
from memory.memory_service import MemoryService
from rules.rules_service import RulesService


REPLY_WITH_RULES_PARAMETERS = {
    "type": "object",
    "properties": {
        "question": {"type": "string", "description": "用户当前的问题原文"},
    },
    "required": ["question"],
}


def _build_memory_notice() -> str:
    """构造记忆召回场景下的规则提示。"""
    return "当前问题涉及记忆事实，建议先调用 search_memory 获取记忆源，再结合规则参考组织回答。"


class ReplyWithRulesRouter(ToolRouter):
    """规则工具入口。"""

    def __init__(
        self,
        rules_service: RulesService,
        memory_service: MemoryService,
        tool_use_policy: ToolUsePolicy,
        agent_name: str = "智能会计",
    ):
        self._rules_service = rules_service
        self._memory_service = memory_service
        self._tool_use_policy = tool_use_policy
        self._agent_name = agent_name

    def get_definition(self) -> ToolDefinition:
        """返回工具定义。"""
        return ToolDefinition(
            name="reply_with_rules",
            description="获取项目当前的会计、报销、审核和记忆相关规则参考，用于回答规则类问题。",
            parameters=REPLY_WITH_RULES_PARAMETERS,
        )

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行规则工具。"""
        question = str(arguments["question"]).strip()
        rules_reference = self._rules_service.build_rules_reference(question)
        payload = self._build_payload(question, rules_reference.rules_text)
        return ToolRouterResponse(
            tool_name="reply_with_rules",
            success=True,
            payload=payload,
        )

    def _build_payload(self, question: str, rules_text: str) -> dict:
        """构造规则工具返回值。"""
        payload = {
            "question": question,
            "rules_reference": rules_text,
        }
        if self._tool_use_policy.is_memory_recall_request(question):
            payload["memory_notice"] = _build_memory_notice()
            return payload
        memory_context = self._memory_service.build_memory_context(
            MemoryContextQuery(agent_name=self._agent_name, query=question)
        )
        if memory_context:
            payload["memory_context"] = memory_context.strip()
        return payload
