"""会计部门共享工作台模型。"""

from dataclasses import dataclass, field

from department.llm_usage import LlmUsage
from department.workbench.collaboration_step import CollaborationStep


@dataclass(frozen=True)
class DepartmentWorkbench:
    """描述一个线程在当前回合内的共享工作台。

    Attributes:
        thread_id: 线程标识。
        original_user_input: 原始用户输入。
        collaboration_steps: 本回合协作步骤列表（用户可见投影）。
        reply_text: crewAI 会计部门最终回复文本（用于审计持久化，不直接暴露给用户）。
        usage: 本回合 LLM token 使用量（内部遥测，不暴露给用户）。
    """

    thread_id: str
    original_user_input: str
    collaboration_steps: list[CollaborationStep] = field(default_factory=list)
    reply_text: str = ""
    usage: LlmUsage | None = None
