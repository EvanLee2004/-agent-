"""工具运行时的数据契约。

这一层把“工具定义”“工具执行结果”“完整运行结果”显式建模，
避免在 Agent 和 Runtime 之间传递松散字典。
"""

import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class ToolDefinition:
    """工具定义。

    Attributes:
        name: 工具名称。
        description: 工具用途说明。
        parameters: JSON Schema 风格的参数定义。
    """

    name: str
    description: str
    parameters: dict[str, Any]

    def to_openai_tool(self) -> dict[str, Any]:
        """转换为 OpenAI-compatible tools 定义。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolExecutionResult:
    """单次工具执行结果。"""

    tool_name: str
    success: bool
    payload: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def to_tool_message_content(self) -> str:
        """转换为 tool message 的 JSON 文本。

        这里强制统一结构，便于模型稳定消费：
        - `success=true` 时主要看 `payload`
        - `success=false` 时主要看 `error_message`
        """
        data = {
            "tool_name": self.tool_name,
            "success": self.success,
            "payload": self.payload,
        }
        if self.error_message:
            data["error_message"] = self.error_message
        return json.dumps(data, ensure_ascii=False)


@dataclass
class ToolRuntimeResult:
    """一次完整工具链路运行结果。"""

    final_reply: str
    executed_tool_names: list[str]
    tool_results: list[ToolExecutionResult]
