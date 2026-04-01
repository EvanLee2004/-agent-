"""会话请求模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConversationRequest:
    """会话请求。

    Attributes:
        user_input: 用户输入。
    """

    user_input: str
