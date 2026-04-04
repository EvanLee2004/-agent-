"""财务部门入口响应模型。"""

from dataclasses import dataclass, field

from department.workbench.collaboration_step import CollaborationStep


@dataclass(frozen=True)
class FinanceDepartmentResponse:
    """描述财务部门对外返回的结果。

    Attributes:
        reply_text: 面向用户的最终回复。
        collaboration_steps: 当前回合协作步骤。
    """

    reply_text: str
    collaboration_steps: list[CollaborationStep] = field(default_factory=list)
