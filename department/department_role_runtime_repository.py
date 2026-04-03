"""角色运行时仓储接口。"""

from abc import ABC, abstractmethod

from department.department_role_request import DepartmentRoleRequest
from department.department_role_response import DepartmentRoleResponse


class DepartmentRoleRuntimeRepository(ABC):
    """定义角色运行时调用接口。"""

    @abstractmethod
    def reply(self, request: DepartmentRoleRequest) -> DepartmentRoleResponse:
        """调用一个角色并返回其结果。

        Args:
            request: 角色运行时请求。

        Returns:
            角色运行时响应。
        """

