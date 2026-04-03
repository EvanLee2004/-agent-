"""财务部门入口响应模型。"""

from dataclasses import dataclass, field

from department.workbench.role_trace import RoleTrace


@dataclass(frozen=True)
class FinanceDepartmentResponse:
    """描述财务部门对外返回的结果。

    Attributes:
        reply_text: 面向用户的最终回复。
        role_traces: 当前回合中各角色的协作轨迹。
    """

    reply_text: str
    role_traces: list[RoleTrace] = field(default_factory=list)
