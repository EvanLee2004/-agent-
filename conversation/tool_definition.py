"""工具定义模型。"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolDefinition:
    """工具定义。

    Attributes:
        name: 工具名称。
        description: 工具说明。
        parameters: JSON Schema 风格参数定义。
    """

    name: str
    description: str
    parameters: dict[str, Any]

    def to_openai_tool(self) -> dict[str, Any]:
        """转换为 OpenAI-compatible 工具定义。

        Returns:
            provider 可直接消费的工具定义。
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
