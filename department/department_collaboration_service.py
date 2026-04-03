"""财务部门角色协作服务。"""

from typing import Optional

from department.department_collaboration_command import DepartmentCollaborationCommand
from department.department_error import DepartmentError
from department.department_role_request import DepartmentRoleRequest
from department.department_role_response import DepartmentRoleResponse
from department.department_role_runtime_repository import DepartmentRoleRuntimeRepository
from department.department_runtime_context import DepartmentRuntimeContext
from department.department_workbench_service import DepartmentWorkbenchService
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog
from department.role_trace import RoleTrace
from department.role_trace_summary_builder import RoleTraceSummaryBuilder


MAX_COLLABORATION_DEPTH = 4


def _build_collaboration_prompt(
    requester_display_name: str,
    target_display_name: str,
    original_user_input: str,
    goal: str,
    context_note: Optional[str],
) -> str:
    """构造角色协作输入。"""
    context_section = context_note.strip() if context_note else "无额外补充上下文。"
    return (
        f"你现在正在智能财务部门内部协作。\n"
        f"请求来源角色：{requester_display_name}\n"
        f"目标角色：{target_display_name}\n"
        f"用户原始请求：{original_user_input}\n"
        f"本次协作目标：{goal}\n"
        f"补充上下文：{context_section}\n\n"
        "请基于你当前角色的专业边界，给出简洁、专业、可执行的结论。"
        "如果事实不足，请明确指出缺少什么；如果需要别的角色配合，你可以继续调用"
        " collaborate_with_department_role，但不要无意义转交。"
    )


class DepartmentCollaborationService:
    """在角色之间发起协作。

    这里不把协作顺序写死成固定 DAG，而是提供一个受控的“角色互相求助”能力。
    协调规则主要来自角色 skill，本服务只负责最小安全边界：禁止自调用、限制深度、
    记录轨迹，并把协作请求转给 DeerFlow 角色运行时。
    """

    def __init__(
        self,
        role_catalog: FinanceDepartmentRoleCatalog,
        runtime_repository: DepartmentRoleRuntimeRepository,
        workbench_service: DepartmentWorkbenchService,
        runtime_context: DepartmentRuntimeContext,
        role_trace_summary_builder: RoleTraceSummaryBuilder,
    ):
        self._role_catalog = role_catalog
        self._runtime_repository = runtime_repository
        self._workbench_service = workbench_service
        self._runtime_context = runtime_context
        self._role_trace_summary_builder = role_trace_summary_builder

    def collaborate(self, command: DepartmentCollaborationCommand) -> DepartmentRoleResponse:
        """执行一次角色协作。

        Args:
            command: 协作命令。

        Returns:
            目标角色返回的结果。
        """
        requester_role_name = self._runtime_context.require_current_role_name()
        thread_id = self._runtime_context.require_current_thread_id()
        current_depth = self._runtime_context.get_current_collaboration_depth()
        self._validate_command(requester_role_name, command, current_depth)
        self._workbench_service.reserve_collaboration(thread_id)
        requester_role = self._role_catalog.get_role(requester_role_name)
        target_role = self._role_catalog.get_role(command.target_role_name)
        role_response = self._runtime_repository.reply(
            DepartmentRoleRequest(
                role_name=target_role.agent_name,
                user_input=_build_collaboration_prompt(
                    requester_role.display_name,
                    target_role.display_name,
                    self._workbench_service.get_original_user_input(thread_id),
                    command.goal,
                    command.context_note,
                ),
                thread_id=thread_id,
                collaboration_depth=current_depth + 1,
            )
        )
        self._workbench_service.record_role_trace(
            thread_id,
            RoleTrace(
                role_name=target_role.agent_name,
                display_name=target_role.display_name,
                requested_by=requester_role.display_name,
                goal=command.goal,
                thinking_summary=self._role_trace_summary_builder.build(role_response.reply_text),
                depth=current_depth + 1,
            ),
        )
        return role_response

    def _validate_command(
        self,
        requester_role_name: str,
        command: DepartmentCollaborationCommand,
        current_depth: int,
    ) -> None:
        """校验协作命令是否合法。"""
        if not command.target_role_name.strip():
            raise DepartmentError("协作请求缺少目标角色")
        if not command.goal.strip():
            raise DepartmentError("协作请求缺少明确目标")
        if requester_role_name == command.target_role_name:
            raise DepartmentError("角色不能向自己发起协作请求")
        if current_depth >= MAX_COLLABORATION_DEPTH:
            raise DepartmentError("当前协作深度过深，请先汇总已有结论")
        self._role_catalog.get_role(command.target_role_name)
