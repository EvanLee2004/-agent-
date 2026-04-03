"""会话响应模型。"""

from dataclasses import dataclass, field

from department.workbench.role_trace import RoleTrace


@dataclass(frozen=True)
class ConversationResponse:
    """会话响应。

    Attributes:
        reply_text: 最终回复文本。
        role_traces: 当前回合角色协作轨迹。
    """

    reply_text: str
    role_traces: list[RoleTrace] = field(default_factory=list)
