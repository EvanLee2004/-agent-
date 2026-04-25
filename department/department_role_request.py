"""角色运行时请求模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DepartmentRoleRequest:
    """描述一次角色调用请求。

    Attributes:
        role_name: 当前要调用的目标角色。
        user_input: 传递给目标角色的输入内容。
        thread_id: 当前线程标识。
        collaboration_depth: 当前协作深度。
        conversation_context: 本项目从历史工作台生成的受控上下文摘要。
        context_refs: 当前轮次解析出的上下文引用。
    """

    role_name: str
    user_input: str
    thread_id: str
    collaboration_depth: int = 0
    conversation_context: str = ""
    context_refs: list[str] | None = None
