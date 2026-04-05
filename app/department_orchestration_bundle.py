"""部门编排装配结果。"""

from dataclasses import dataclass

from department.finance_department_service import FinanceDepartmentService
from department.workbench.department_workbench_service import DepartmentWorkbenchService


@dataclass(frozen=True)
class DepartmentOrchestrationBundle:
    """部门协作层对外暴露的核心对象。

    FinanceDepartmentService 作为唯一入口，通过 DeerFlow task 工具驱动
    subagent 协作；workbench_service 提供 API 历史查询能力。
    """

    finance_department_service: FinanceDepartmentService
    workbench_service: DepartmentWorkbenchService
