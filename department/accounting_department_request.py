"""会计部门请求模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountingDepartmentRequest:
    """描述一轮会计部门请求。"""

    user_input: str
    thread_id: str
