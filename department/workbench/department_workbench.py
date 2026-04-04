"""财务部门共享工作台模型。"""

from dataclasses import dataclass, field

from department.workbench.collaboration_step import CollaborationStep


@dataclass(frozen=True)
class DepartmentWorkbench:
    """描述一个线程在当前回合内的共享工作台。

    阶段 4 重定义：工作台不再记录"角色调用角色"的递归轨迹，而是记录用户回合的
    原始目标和系统基于 DeerFlow 原生 task/subagent 机制得出的协作结论。
    """

    thread_id: str
    original_user_input: str
    collaboration_steps: list[CollaborationStep] = field(default_factory=list)
