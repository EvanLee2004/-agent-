"""财务部门共享工作台模型。"""

from dataclasses import dataclass, field

from department.workbench.role_trace import RoleTrace


@dataclass(frozen=True)
class DepartmentWorkbench:
    """描述一个线程在当前回合内的共享工作台。

    Attributes:
        thread_id: 当前会话线程标识。
        original_user_input: 用户当前回合的原始输入。
        collaboration_count: 本回合累计发生的角色协作次数。
        role_traces: 当前回合已经产生的协作轨迹。
    """

    thread_id: str
    original_user_input: str
    collaboration_count: int = 0
    role_traces: list[RoleTrace] = field(default_factory=list)
