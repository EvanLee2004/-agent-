"""财务部门入口请求模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FinanceDepartmentRequest:
    """描述一轮财务部门入口请求。

    Attributes:
        user_input: 用户原始输入。
        thread_id: 当前会话线程标识。
    """

    user_input: str
    thread_id: str

