"""会话请求模型。"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ConversationRequest:
    """会话请求。

    Attributes:
        user_input: 用户输入。
        thread_id: 会话线程标识；同一线程可保留底层 Agent 的上下文。
    """

    user_input: str
    thread_id: Optional[str] = None
