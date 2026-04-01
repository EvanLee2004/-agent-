"""LLM 工具调用模型。"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LlmToolCall:
    """模型返回的单次工具调用。

    Attributes:
        call_id: provider 返回的工具调用标识。
        tool_name: 工具名称。
        arguments: 已解析好的工具参数。
        raw_arguments: 原始工具参数字符串。
    """

    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    raw_arguments: str
