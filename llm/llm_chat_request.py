"""LLM 聊天请求模型。"""

from dataclasses import dataclass, field

from llm.llm_message import LlmMessage


@dataclass(frozen=True)
class LlmChatRequest:
    """带工具定义的 LLM 请求。

    Attributes:
        messages: 消息历史。
        tools: 工具 schema 列表。
        tool_choice: 工具调用策略。
        temperature: 温度参数。
        timeout: 超时秒数。
    """

    messages: list[LlmMessage]
    tools: list[dict]
    tool_choice: str = "auto"
    temperature: float = 0.3
    timeout: int = 30
