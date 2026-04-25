"""会计部门会话上下文模型。"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConversationContext:
    """描述传入 crewAI 本轮任务的受控上下文。

    Attributes:
        summary: 由本项目从 workbench 历史生成的短摘要。
        context_refs: 可被 API 暴露的上下文引用标识，例如 `voucher:12`。
    """

    summary: str = ""
    context_refs: list[str] = field(default_factory=list)
