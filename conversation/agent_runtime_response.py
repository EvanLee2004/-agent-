"""会话运行时响应模型。"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentRuntimeResponse:
    """描述底层 Agent 运行时返回的结果。

    Attributes:
        reply_text: 面向最终用户的回复文本。
        executed_tool_names: 本轮运行中实际执行过的工具名列表。
    """

    reply_text: str
    executed_tool_names: list[str] = field(default_factory=list)
