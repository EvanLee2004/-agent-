"""财务部门入口服务。"""

from department.department_role_request import DepartmentRoleRequest
from department.department_role_runtime_repository import DepartmentRoleRuntimeRepository
from department.department_workbench_service import DepartmentWorkbenchService
from department.finance_department_request import FinanceDepartmentRequest
from department.finance_department_response import FinanceDepartmentResponse
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog
from department.role_trace import RoleTrace
from department.role_trace_summary_builder import RoleTraceSummaryBuilder


class FinanceDepartmentService:
    """协调财务部门入口回合。

    该服务的职责不是替角色做专业判断，而是负责“开启一回合部门协作”：
    初始化工作台、拉起入口角色、收集本回合轨迹并汇总为统一响应。
    角色如何互相沟通，主要由它们的 skill 和协作工具决定，而不是写死在这里。
    """

    def __init__(
        self,
        role_catalog: FinanceDepartmentRoleCatalog,
        role_runtime_repository: DepartmentRoleRuntimeRepository,
        workbench_service: DepartmentWorkbenchService,
        role_trace_summary_builder: RoleTraceSummaryBuilder,
    ):
        self._role_catalog = role_catalog
        self._role_runtime_repository = role_runtime_repository
        self._workbench_service = workbench_service
        self._role_trace_summary_builder = role_trace_summary_builder

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
        self._workbench_service.record_role_trace(
            request.thread_id,
            RoleTrace(
                role_name=entry_role.agent_name,
                display_name=entry_role.display_name,
                requested_by=None,
                goal=request.user_input,
                thinking_summary=self._role_trace_summary_builder.build(role_response.reply_text),
                depth=0,
            ),
        )
        return FinanceDepartmentResponse(
            reply_text=role_response.reply_text,
            role_traces=self._workbench_service.list_role_traces(request.thread_id),
        )
