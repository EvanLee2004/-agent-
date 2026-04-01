"""会话响应模型。"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConversationResponse:
    """会话响应。

    Attributes:
        reply_text: 最终回复文本。
        executed_tool_names: 已执行工具名列表。
    """

    reply_text: str
    executed_tool_names: list[str] = field(default_factory=list)
