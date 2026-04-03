"""部门编排装配结果。"""

from dataclasses import dataclass

from department.collaboration.department_collaboration_service import DepartmentCollaborationService
from department.finance_department_service import FinanceDepartmentService


@dataclass(frozen=True)
class DepartmentOrchestrationBundle:
    """描述部门协作层对外暴露的核心对象。

    会话主链路只需要两个部门级对象：一个对外承接整轮协作的入口服务，一个供
    `collaborate_with_department_role` 工具继续向下转派任务的协作服务。把它们收成
    bundle 后，装配层不会再需要知道工作台、运行时上下文等中间细节。
    """

    finance_department_service: FinanceDepartmentService
    collaboration_service: DepartmentCollaborationService
