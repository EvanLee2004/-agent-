"""LLM 消息模型。"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class LlmMessage:
    """LLM 消息。

    Attributes:
        role: 消息角色。
        content: 消息正文。
        tool_call_id: 工具消息关联的调用标识。
        tool_calls: assistant 消息携带的原始工具调用定义。
    """

    role: str
    content: str
    tool_call_id: Optional[str] = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为 OpenAI-compatible 消息字典。

        Returns:
            适合 provider 直接消费的消息字典。
        """
        payload: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
        }
        if self.tool_call_id:
            payload["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            payload["tool_calls"] = self.tool_calls
        return payload
