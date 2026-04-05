"""角色运行时响应模型。"""

from dataclasses import dataclass, field

from department.llm_usage import LlmUsage
from department.workbench.execution_event import ExecutionEvent


@dataclass(frozen=True)
class DepartmentRoleResponse:
    """描述一次角色调用结果。

    Attributes:
        role_name: 产生本次结果的角色名。
        reply_text: 该角色给出的自然语言结果（最后一个非空 AI 文本）。
        collaboration_depth: 产生本次结果时所处的协作深度。
        execution_events: 本次调用过程中收集到的执行事件列表，
            用于生成用户可见的协作摘要。不包含原始长文本 thinking。
        usage: 本次 DeerFlow turn 的 LLM token 使用量（内部遥测，不暴露给用户）。
    """

    role_name: str
    reply_text: str
    collaboration_depth: int
    execution_events: list[ExecutionEvent] = field(default_factory=list)
    usage: LlmUsage | None = None

