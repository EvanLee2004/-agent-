"""会计部门响应模型。"""

from dataclasses import dataclass, field

from department.workbench.collaboration_step import CollaborationStep


@dataclass(frozen=True)
class AccountingDepartmentResponse:
    """会计部门对外响应。"""

    reply_text: str
    collaboration_steps: list[CollaborationStep] = field(default_factory=list)
