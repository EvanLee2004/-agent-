"""工具路由响应模型。"""

import json
from dataclasses import dataclass, field
from json import JSONDecodeError
from typing import Any


@dataclass(frozen=True)
class ToolRouterResponse:
    """工具路由响应。

    Attributes:
        tool_name: 工具名称。
        success: 是否成功。
        payload: 成功时的结构化结果。
        error_message: 失败原因。
        voucher_ids: 本次工具结果涉及的凭证 ID 列表。
        context_refs: 本次工具结果可供后续多轮引用的上下文标识。
    """

    tool_name: str
    success: bool
    payload: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    voucher_ids: list[int] = field(default_factory=list)
    context_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为稳定 envelope 字典。

        Returns:
            面向 Agent、API 和历史投影的统一工具结果结构。
        """
        data = {
            "tool_name": self.tool_name,
            "success": self.success,
            "payload": self.payload,
            "error_message": self.error_message,
            "voucher_ids": self.voucher_ids,
            "context_refs": self.context_refs,
        }
        return data

    def to_tool_message_content(self) -> str:
        """转换为工具消息文本。

        crewAI 工具返回值必须是可被模型读取的文本。这里继续返回 JSON 字符串，
        但 JSON 内部已经是稳定 envelope，API 层可以解析该结构化结果，不再需要
        从最终自然语言回复里用正则猜凭证号。

        Returns:
            统一结构的 JSON 文本。
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolRouterResponse":
        """从 envelope 字典恢复工具响应。

        Args:
            data: 工具结果 envelope。

        Returns:
            工具响应对象。
        """
        raw_voucher_ids = data.get("voucher_ids", [])
        if not isinstance(raw_voucher_ids, list):
            raw_voucher_ids = []
        raw_context_refs = data.get("context_refs", [])
        if not isinstance(raw_context_refs, list):
            raw_context_refs = []

        return cls(
            tool_name=str(data.get("tool_name") or ""),
            success=bool(data.get("success")),
            payload=data.get("payload") if isinstance(data.get("payload"), dict) else {},
            error_message=(
                str(data["error_message"])
                if data.get("error_message") is not None
                else None
            ),
            voucher_ids=[
                int(item)
                for item in raw_voucher_ids
                if isinstance(item, int) or str(item).isdigit()
            ],
            context_refs=[
                str(item)
                for item in raw_context_refs
                if str(item).strip()
            ],
        )

    @classmethod
    def from_tool_message_content(cls, raw_content: str) -> "ToolRouterResponse | None":
        """从工具消息文本中解析响应。

        Args:
            raw_content: 工具返回给 crewAI 的 JSON 文本。

        Returns:
            解析成功时返回工具响应；非 JSON 或结构不匹配时返回 None。
        """
        try:
            data = json.loads(raw_content)
        except (JSONDecodeError, TypeError):
            return None
        if not isinstance(data, dict):
            return None
        if "tool_name" not in data or "success" not in data:
            return None
        return cls.from_dict(data)
