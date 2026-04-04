"""规则工具入口。"""

from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse
from rules.rules_service import RulesService


class ReplyWithRulesRouter(ToolRouter):
    """规则工具入口。

    切换至 DeerFlow 原生记忆后，记忆上下文由 DeerFlow 自动注入 system prompt，
    不再需要在工具层手动注入 memory_context 或提示 agent 调用 search_memory。
    该路由只负责加载规则参考文本并返回给 DeerFlow，记忆召回由 DeerFlow 记忆模块
    在上游自动完成。
    """

    def __init__(self, rules_service: RulesService):
        self._rules_service = rules_service

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行规则工具。

        Args:
            arguments: 包含 `question` 字段的工具参数。

        Returns:
            含规则参考文本的工具响应。
        """
        question = str(arguments["question"]).strip()
        rules_reference = self._rules_service.build_rules_reference(question)
        return ToolRouterResponse(
            tool_name="reply_with_rules",
            success=True,
            payload={
                "question": question,
                "rules_reference": rules_reference.rules_text,
            },
        )
