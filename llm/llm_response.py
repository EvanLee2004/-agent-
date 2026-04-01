"""LLM 响应模型。"""

from dataclasses import dataclass, field
from typing import Optional

from llm.llm_message import LlmMessage
from llm.llm_tool_call import LlmToolCall


@dataclass(frozen=True)
class LlmResponse:
    """统一后的 LLM 响应。

    Attributes:
        content: 文本响应内容。
        usage: token 使用统计。
        model_name: 实际使用的模型名。
        success: 是否成功。
        error_message: 失败原因。
        tool_calls: 工具调用列表。
        finish_reason: provider 返回的 finish reason。
        assistant_message: 归一化后的 assistant 消息。
    """

    content: str
    usage: dict
    model_name: str
    success: bool = True
    error_message: Optional[str] = None
    tool_calls: list[LlmToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None
    assistant_message: Optional[LlmMessage] = None
