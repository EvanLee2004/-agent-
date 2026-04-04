"""部门编排装配结果。"""

from dataclasses import dataclass

from department.finance_department_service import FinanceDepartmentService


@dataclass(frozen=True)
class DepartmentOrchestrationBundle:
    """描述部门协作层对外暴露的核心对象。

    阶段 3：多 agent 协作已迁移至 DeerFlow 原生 task/subagent 机制，
    DepartmentCollaborationService 不再作为独立服务暴露。FinanceDepartmentService
    作为唯一入口，通过 DeerFlow task 工具驱动 subagent 协作。
    """

    finance_department_service: FinanceDepartmentService
