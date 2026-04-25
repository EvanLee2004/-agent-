"""会计部门入口服务。"""

from department.accounting_department_request import AccountingDepartmentRequest
from department.accounting_department_response import AccountingDepartmentResponse
from department.conversation_context_service import ConversationContextService
from department.accounting_department_role_catalog import AccountingDepartmentRoleCatalog
from department.department_role_request import DepartmentRoleRequest
from department.department_role_runtime_repository import DepartmentRoleRuntimeRepository
from department.workbench.collaboration_step_factory import CollaborationStepFactory
from department.workbench.department_workbench_service import DepartmentWorkbenchService


class AccountingDepartmentService:
    """协调一轮会计部门处理。

    服务层只负责产品级流程：开启回合、调用入口角色、投影协作步骤、落库历史。
    crewAI 的 Agent/Task/Crew 构造细节留在 runtime/crewai，避免 app/conversation
    直接依赖第三方运行时。
    """

    def __init__(
        self,
        role_catalog: AccountingDepartmentRoleCatalog,
        role_runtime_repository: DepartmentRoleRuntimeRepository,
        workbench_service: DepartmentWorkbenchService,
        collaboration_step_factory: CollaborationStepFactory,
        conversation_context_service: ConversationContextService,
    ):
        self._role_catalog = role_catalog
        self._role_runtime_repository = role_runtime_repository
        self._workbench_service = workbench_service
        self._collaboration_step_factory = collaboration_step_factory
        self._conversation_context_service = conversation_context_service

    def reply(
        self,
        request: AccountingDepartmentRequest,
    ) -> AccountingDepartmentResponse:
        """处理一轮会计部门请求。"""
        entry_role = self._role_catalog.get_entry_role()
        conversation_context = self._conversation_context_service.build_context(
            request.thread_id,
            request.user_input,
        )
        self._workbench_service.start_turn(request.thread_id, request.user_input)
        role_response = self._role_runtime_repository.reply(
            DepartmentRoleRequest(
                role_name=entry_role.agent_name,
                user_input=request.user_input,
                thread_id=request.thread_id,
                collaboration_depth=0,
                conversation_context=conversation_context.summary,
                context_refs=conversation_context.context_refs,
            )
        )
        collaboration_steps = self._collaboration_step_factory.build_from_events(
            goal=request.user_input,
            execution_events=role_response.execution_events,
            final_reply_text=role_response.reply_text,
        )
        for step in collaboration_steps:
            self._workbench_service.record_collaboration_step(request.thread_id, step)
        self._workbench_service.finalize_turn(
            request.thread_id,
            role_response.reply_text,
            role_response.usage,
            execution_events=role_response.execution_events,
        )
        return AccountingDepartmentResponse(
            reply_text=role_response.reply_text,
            # 对话响应只返回“本回合”的协作步骤；跨回合历史由 workbench 查询接口负责。
            # 这样可以避免第二轮对话把第一轮步骤再次塞进 API/CLI 当前响应，保持响应契约清晰。
            collaboration_steps=collaboration_steps,
            tool_results=role_response.tool_results,
            context_refs=role_response.context_refs,
        )
