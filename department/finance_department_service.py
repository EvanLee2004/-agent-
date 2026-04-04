"""财务部门入口服务。"""

from department.department_role_request import DepartmentRoleRequest
from department.department_role_runtime_repository import DepartmentRoleRuntimeRepository
from department.finance_department_request import FinanceDepartmentRequest
from department.finance_department_response import FinanceDepartmentResponse
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog
from department.workbench.collaboration_step_factory import CollaborationStepFactory
from department.workbench.department_workbench_service import DepartmentWorkbenchService


class FinanceDepartmentService:
    """协调财务部门入口回合。

    阶段 4 重定义：该服务的职责改为"开启一回合 DeerFlow 原生协作"：
    初始化工作台、拉起 DeerFlow coordinator 角色、收集协作步骤并汇总为统一响应。

    角色如何沟通由 DeerFlow task/subagent 机制决定（不在本服务层感知），
    本服务只负责记录"用户做了什么、系统得出什么结论"的协作步骤。
    """

    def __init__(
        self,
        role_catalog: FinanceDepartmentRoleCatalog,
        role_runtime_repository: DepartmentRoleRuntimeRepository,
        workbench_service: DepartmentWorkbenchService,
        collaboration_step_factory: CollaborationStepFactory,
    ):
        self._role_catalog = role_catalog
        self._role_runtime_repository = role_runtime_repository
        self._workbench_service = workbench_service
        self._collaboration_step_factory = collaboration_step_factory

    def reply(self, request: FinanceDepartmentRequest) -> FinanceDepartmentResponse:
        """处理一轮财务部门入口请求。"""
        entry_role = self._role_catalog.get_entry_role()
        self._workbench_service.start_turn(request.thread_id, request.user_input)
        role_response = self._role_runtime_repository.reply(
            DepartmentRoleRequest(
                role_name=entry_role.agent_name,
                user_input=request.user_input,
                thread_id=request.thread_id,
                collaboration_depth=0,
            )
        )
        # 阶段 4：协作步骤来自 DeerFlow stream 事件，而非 reply_text 的二次压缩。
        # 每个 ExecutionEvent 对应一个可识别的执行动作（工具调用、任务委托等），
        # 由 CollaborationStepFactory 转换为对用户友好的协作步骤。
        collaboration_steps = self._collaboration_step_factory.build_from_events(
            goal=request.user_input,
            execution_events=role_response.execution_events,
            final_reply_text=role_response.reply_text,
        )
        for step in collaboration_steps:
            self._workbench_service.record_collaboration_step(request.thread_id, step)
        return FinanceDepartmentResponse(
            reply_text=role_response.reply_text,
            collaboration_steps=self._workbench_service.list_collaboration_steps(request.thread_id),
        )
