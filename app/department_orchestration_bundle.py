"""会计部门编排装配结果。"""

from dataclasses import dataclass

from department.accounting_department_service import AccountingDepartmentService
from department.workbench.department_workbench_service import DepartmentWorkbenchService


@dataclass(frozen=True)
class DepartmentOrchestrationBundle:
    """会计部门协作层对外暴露的核心对象。

    AccountingDepartmentService 作为唯一入口，内部通过 crewAI 运行时执行固定
    会计核算流程；workbench_service 提供 API 历史查询能力。
    """

    accounting_department_service: AccountingDepartmentService
    workbench_service: DepartmentWorkbenchService
