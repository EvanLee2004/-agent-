"""工具循环结果模型。"""

from dataclasses import dataclass, field

from conversation.tool_router_response import ToolRouterResponse


@dataclass(frozen=True)
class ToolLoopResult:
    """工具循环结果。

    Attributes:
        final_reply: 最终回复文本。
        executed_tool_names: 执行过的工具名列表。
        tool_router_responses: 工具执行结果列表。
    """

    final_reply: str
    executed_tool_names: list[str]
    tool_router_responses: list[ToolRouterResponse] = field(default_factory=list)
