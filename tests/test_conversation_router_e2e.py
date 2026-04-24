"""会计部门会话主链路测试。"""

import tempfile
import unittest
from pathlib import Path

from conversation.conversation_request import ConversationRequest
from conversation.conversation_router import ConversationRouter
from conversation.conversation_service import ConversationService
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from department.accounting_department_request import AccountingDepartmentRequest
from department.accounting_department_role_catalog import AccountingDepartmentRoleCatalog
from department.accounting_department_service import AccountingDepartmentService
from department.department_role_response import DepartmentRoleResponse
from department.department_role_runtime_repository import DepartmentRoleRuntimeRepository
from department.workbench.collaboration_step_factory import CollaborationStepFactory
from department.workbench.department_workbench_service import DepartmentWorkbenchService
from department.workbench.execution_event import ExecutionEvent
from department.workbench.execution_event_type import ExecutionEventType
from department.workbench.final_reply_summary_builder import FinalReplySummaryBuilder
from department.workbench.sqlite_department_workbench_repository import (
    SQLiteDepartmentWorkbenchRepository,
)


class FakeRoleRuntimeRepository(DepartmentRoleRuntimeRepository):
    """测试用角色运行时仓储。"""

    def __init__(self):
        self.requests = []

    def reply(self, request) -> DepartmentRoleResponse:
        """返回固定会计部门事件。"""
        self.requests.append(request)
        return DepartmentRoleResponse(
            role_name=request.role_name,
            reply_text="凭证已记录，凭证号为 1。",
            collaboration_depth=request.collaboration_depth,
            execution_events=[
                ExecutionEvent(
                    event_type=ExecutionEventType.TASK_CALL,
                    tool_name="accounting_intake",
                    summary="执行 accounting_intake",
                ),
                ExecutionEvent(
                    event_type=ExecutionEventType.TOOL_CALL,
                    tool_name="record_voucher",
                    summary="调用 record_voucher",
                ),
                ExecutionEvent(
                    event_type=ExecutionEventType.TOOL_RESULT,
                    tool_name="record_voucher",
                    summary="凭证已记录",
                ),
                ExecutionEvent(
                    event_type=ExecutionEventType.FINAL_REPLY,
                    tool_name="",
                    summary="凭证已记录，凭证号为 1。",
                ),
            ],
        )


class AccountingConversationRouterE2ETest(unittest.TestCase):
    """验证会话入口到会计部门服务的主路径。"""

    def test_router_records_collaboration_steps_and_history(self):
        """会话回复应生成协作步骤并落入工作台历史。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_repository = FakeRoleRuntimeRepository()
            workbench_service = DepartmentWorkbenchService(
                SQLiteDepartmentWorkbenchRepository(Path(temp_dir) / "workbench.db")
            )
            department_service = AccountingDepartmentService(
                role_catalog=AccountingDepartmentRoleCatalog(),
                role_runtime_repository=runtime_repository,
                workbench_service=workbench_service,
                collaboration_step_factory=CollaborationStepFactory(
                    FinalReplySummaryBuilder()
                ),
            )
            router = ConversationRouter(
                ConversationService(
                    accounting_department_service=department_service,
                    reply_text_sanitizer=ReplyTextSanitizer(),
                )
            )

            response = router.handle(
                ConversationRequest(
                    user_input="记录一笔收入凭证",
                    thread_id="thread-1",
                )
            )

            self.assertEqual(response.reply_text, "凭证已记录，凭证号为 1。")
            self.assertEqual(runtime_repository.requests[0].role_name, "accounting-manager")
            self.assertEqual(response.collaboration_steps[0].summary, "判断会计任务")
            self.assertIn(
                "记录凭证",
                [step.summary for step in response.collaboration_steps],
            )
            turns = workbench_service.list_turns_with_steps("thread-1")
            self.assertEqual(len(turns), 1)
            self.assertEqual(turns[0]["reply_text"], "凭证已记录，凭证号为 1。")


if __name__ == "__main__":
    unittest.main()
