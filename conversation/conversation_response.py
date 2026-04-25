"""会话响应模型。"""

from dataclasses import dataclass, field

from conversation.tool_router_response import ToolRouterResponse
from department.workbench.collaboration_step import CollaborationStep


@dataclass(frozen=True)
class ConversationResponse:
    """会话响应。

    Attributes:
        reply_text: 最终回复文本。
        collaboration_steps: 当前回合协作步骤。
        tool_results: 当前回合结构化工具结果。
        context_refs: 当前回合解析出的上下文引用。
    """

    reply_text: str
    collaboration_steps: list[CollaborationStep] = field(default_factory=list)
    tool_results: list[ToolRouterResponse] = field(default_factory=list)
    context_refs: list[str] = field(default_factory=list)
