"""工具路由响应模型。"""

import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class ToolRouterResponse:
    """工具路由响应。

    Attributes:
        tool_name: 工具名称。
        success: 是否成功。
        payload: 成功时的结构化结果。
        error_message: 失败原因。
    """

    tool_name: str
    success: bool
    payload: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def to_tool_message_content(self) -> str:
        """转换为工具消息文本。

        Returns:
            统一结构的 JSON 文本。
        """
        data = {
            "tool_name": self.tool_name,
            "success": self.success,
            "payload": self.payload,
        }
        if self.error_message:
            data["error_message"] = self.error_message
        return json.dumps(data, ensure_ascii=False)
