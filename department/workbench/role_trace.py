"""角色协作轨迹模型。"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RoleTrace:
    """描述一次角色协作轨迹。

    Attributes:
        role_name: 角色在系统中的稳定标识。
        display_name: 面向产品界面的角色展示名。
        requested_by: 发起本次协作的上游角色；用户入口角色则为 None。
        goal: 本次角色处理的目标摘要。
        thinking_summary: 面向用户展示的思考摘要，不暴露原始推理全文。
        depth: 当前协作深度，入口角色为 0。
    """

    role_name: str
    display_name: str
    requested_by: Optional[str]
    goal: str
    thinking_summary: str
    depth: int

