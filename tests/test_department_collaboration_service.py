"""财务部门协作服务测试。"""

import unittest

from department.department_collaboration_command import DepartmentCollaborationCommand
from department.department_collaboration_service import DepartmentCollaborationService
from department.department_error import DepartmentError
from department.department_role_request import DepartmentRoleRequest
from department.department_role_response import DepartmentRoleResponse
from department.department_role_runtime_repository import DepartmentRoleRuntimeRepository
from department.department_runtime_context import DepartmentRuntimeContext
from department.department_workbench_service import DepartmentWorkbenchService
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog
from department.finance_department_service import FinanceDepartmentService
from department.finance_department_request import FinanceDepartmentRequest
from department.in_memory_department_workbench_repository import InMemoryDepartmentWorkbenchRepository


class FakeDepartmentRoleRuntimeRepository(DepartmentRoleRuntimeRepository):
    """用于验证部门协作服务的运行时替身。"""

    def __init__(self):
        self.calls: list[DepartmentRoleRequest] = []

    def reply(self, request: DepartmentRoleRequest) -> DepartmentRoleResponse:
        """记录请求并返回预设响应。"""
        self.calls.append(request)
        return DepartmentRoleResponse(
            role_name=request.role_name,
            reply_text=f"{request.role_name} 已处理：{request.user_input}",
            collaboration_depth=request.collaboration_depth,
        )


class DepartmentCollaborationServiceTest(unittest.TestCase):
    """验证财务部门协作逻辑。"""

    def test_collaboration_service_records_trace_for_target_role(self):
        """验证角色协作会记录目标角色轨迹。"""
        runtime_context = DepartmentRuntimeContext()
        workbench_service = DepartmentWorkbenchService(
            InMemoryDepartmentWorkbenchRepository()
        )
        workbench_service.start_turn("thread-1", "用户想确认这笔款是否已经支付")
        runtime_repository = FakeDepartmentRoleRuntimeRepository()
        service = DepartmentCollaborationService(
            role_catalog=FinanceDepartmentRoleCatalog(),
            runtime_repository=runtime_repository,
            workbench_service=workbench_service,
            runtime_context=runtime_context,
        )

        with runtime_context.open_scope("finance-coordinator", "thread-1", 0):
            response = service.collaborate(
                DepartmentCollaborationCommand(
                    target_role_name="finance-cashier",
                    goal="确认客户拜访午餐报销是否已经付款",
                    context_note="用户提到120元客户拜访午餐费。",
                )
            )

        self.assertEqual(response.role_name, "finance-cashier")
        self.assertEqual(len(workbench_service.list_role_traces("thread-1")), 1)
        self.assertEqual(workbench_service.list_role_traces("thread-1")[0].requested_by, "CoordinatorAgent")

    def test_collaboration_service_rejects_self_collaboration(self):
        """验证角色不能请求自己重复处理。"""
        runtime_context = DepartmentRuntimeContext()
        workbench_service = DepartmentWorkbenchService(
            InMemoryDepartmentWorkbenchRepository()
        )
        workbench_service.start_turn("thread-2", "测试")
        service = DepartmentCollaborationService(
            role_catalog=FinanceDepartmentRoleCatalog(),
            runtime_repository=FakeDepartmentRoleRuntimeRepository(),
            workbench_service=workbench_service,
            runtime_context=runtime_context,
        )

        with runtime_context.open_scope("finance-audit", "thread-2", 0):
            with self.assertRaises(DepartmentError):
                service.collaborate(
                    DepartmentCollaborationCommand(
                        target_role_name="finance-audit",
                        goal="请再审一遍自己",
                    )
                )

    def test_finance_department_service_collects_entry_role_trace(self):
        """验证部门入口服务会记录入口角色轨迹。"""
        role_catalog = FinanceDepartmentRoleCatalog()
        workbench_service = DepartmentWorkbenchService(
            InMemoryDepartmentWorkbenchRepository()
        )
        runtime_repository = FakeDepartmentRoleRuntimeRepository()
        service = FinanceDepartmentService(
            role_catalog=role_catalog,
            role_runtime_repository=runtime_repository,
            workbench_service=workbench_service,
        )

        response = service.reply(
            FinanceDepartmentRequest(
                user_input="你好",
                thread_id="thread-3",
            )
        )

        self.assertEqual(response.role_traces[-1].display_name, "CoordinatorAgent")
        self.assertEqual(runtime_repository.calls[0].role_name, "finance-coordinator")
