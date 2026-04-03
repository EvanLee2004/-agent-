"""角色协作命令。"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DepartmentCollaborationCommand:
    """描述一次角色协作请求。

    Attributes:
        target_role_name: 目标角色名。
        goal: 希望目标角色解决的具体目标。
        context_note: 可选的补充上下文。
    """

    target_role_name: str
    goal: str
    context_note: Optional[str] = None

