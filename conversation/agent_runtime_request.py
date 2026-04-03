"""会话运行时请求模型。"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AgentRuntimeRequest:
    """描述一次发往底层 Agent 运行时的请求。

    之所以把运行时请求独立成模型，而不是直接把 `ConversationRequest`
    透传给底层，是为了把“对外会话协议”和“底层 Agent 引擎协议”解耦。
    这样后续从单角色入口演进到多角色协同时，外层 CLI/API 不需要跟着一起改。

    Attributes:
        user_input: 用户原始输入文本。
        thread_id: DeerFlow 会话线程标识；同一线程可复用上下文和检查点。
    """

    user_input: str
    thread_id: Optional[str] = None
