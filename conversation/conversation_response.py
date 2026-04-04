"""会话响应模型。"""

from dataclasses import dataclass, field

from department.workbench.collaboration_step import CollaborationStep


@dataclass(frozen=True)
class ConversationResponse:
    """会话响应。

    Attributes:
        reply_text: 最终回复文本。
        collaboration_steps: 当前回合协作步骤。
    """

    reply_text: str
    collaboration_steps: list[CollaborationStep] = field(default_factory=list)
