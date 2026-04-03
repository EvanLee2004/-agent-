"""角色协作工具入口。"""

from department.department_collaboration_command import DepartmentCollaborationCommand
from department.department_collaboration_service import DepartmentCollaborationService
from department.department_error import DepartmentError
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse


class CollaborateWithDepartmentRoleRouter(ToolRouter):
    """角色协作工具入口。"""

    def __init__(self, collaboration_service: DepartmentCollaborationService):
        self._collaboration_service = collaboration_service

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行角色协作路由。"""
        try:
            role_response = self._collaboration_service.collaborate(
                DepartmentCollaborationCommand(
                    target_role_name=str(arguments["target_role_name"]).strip(),
                    goal=str(arguments["goal"]).strip(),
                    context_note=str(arguments.get("context_note", "")).strip() or None,
                )
            )
            return ToolRouterResponse(
                tool_name="collaborate_with_department_role",
                success=True,
                payload={
                    "role_name": role_response.role_name,
                    "reply_text": role_response.reply_text,
                    "collaboration_depth": role_response.collaboration_depth,
                },
            )
        except DepartmentError as error:
            return ToolRouterResponse(
                tool_name="collaborate_with_department_role",
                success=False,
                error_message=f"部门协作失败: {str(error)}",
            )

