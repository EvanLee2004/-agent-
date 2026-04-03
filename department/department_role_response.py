"""角色运行时响应模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DepartmentRoleResponse:
    """描述一次角色调用结果。

    Attributes:
        role_name: 产生本次结果的角色名。
        reply_text: 该角色给出的自然语言结果。
        collaboration_depth: 产生本次结果时所处的协作深度。
    """

    role_name: str
    reply_text: str
    collaboration_depth: int

