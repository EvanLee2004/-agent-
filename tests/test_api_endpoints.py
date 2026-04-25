"""会计部门 API 契约测试。"""

import unittest

from fastapi.testclient import TestClient

from api.accounting_app import create_app
from conversation.conversation_response import ConversationResponse
from conversation.tool_router_response import ToolRouterResponse
from department.workbench.collaboration_step import CollaborationStep
from department.workbench.collaboration_step_type import CollaborationStepType
from department.workbench.execution_event import ExecutionEvent
from department.workbench.execution_event_type import ExecutionEventType


class FakeConversationHandler:
    """测试用会话处理器。"""

    def __init__(self):
        self.requests = []

    def handle(self, request):
        """返回固定会计部门响应。"""
        self.requests.append(request)
        return ConversationResponse(
            reply_text="凭证已记录，凭证号为 12。建议下一步复核。",
            collaboration_steps=[
                CollaborationStep(
                    goal=request.user_input,
                    step_type=CollaborationStepType.TOOL_CALL,
                    tool_name="record_voucher",
                    summary="记录凭证",
                )
            ],
            tool_results=[
                ToolRouterResponse(
                    tool_name="record_voucher",
                    success=True,
                    payload={"voucher_id": 12},
                    voucher_ids=[12],
                    context_refs=["voucher:12"],
                )
            ],
            context_refs=["voucher:12"],
        )


class FakeWorkbenchService:
    """测试用工作台服务。"""

    def list_turns_with_steps(self, thread_id: str):
        """返回固定历史。"""
        return [
            {
                "original_user_input": "记录收入凭证",
                "reply_text": "凭证已记录，凭证号为 12。",
                "collaboration_steps": [
                    CollaborationStep(
                        goal="记录收入凭证",
                        step_type=CollaborationStepType.TOOL_RESULT,
                        tool_name="record_voucher",
                        summary="凭证已记录",
                    )
                ],
            }
        ]

    def list_collaboration_steps(self, thread_id: str):
        """返回固定协作步骤。"""
        return [
            CollaborationStep(
                goal="复核凭证",
                step_type=CollaborationStepType.TOOL_CALL,
                tool_name="audit_voucher",
                summary="审核凭证",
            )
        ]

    def list_execution_events_with_context(self, thread_id: str):
        """返回固定执行事件。"""
        event = ExecutionEvent(
            event_type=ExecutionEventType.TOOL_CALL,
            tool_name="audit_voucher",
            summary="调用 audit_voucher",
        )
        return [
            {
                "event_type": event.event_type.value,
                "tool_name": event.tool_name,
                "summary": event.summary,
                "turn_index": 1,
                "event_sequence": 1,
            }
        ]


class AccountingApiEndpointTest(unittest.TestCase):
    """验证 API 已切换为会计部门契约。"""

    def setUp(self):
        handler = FakeConversationHandler()
        app = create_app(
            conversation_handler=handler,
            workbench_service=FakeWorkbenchService(),
        )
        self.handler = handler
        self.client = TestClient(app)

    def test_reply_returns_accounting_response_model(self):
        """回复接口返回会计核算字段。"""
        response = self.client.post(
            "/api/accounting/thread-1/reply",
            json={"user_input": "记录收入凭证"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["voucher_ids"], [12])
        self.assertEqual(data["errors"], [])
        self.assertIsNone(data["audit_summary"])
        self.assertEqual(data["tool_results"][0]["tool_name"], "record_voucher")
        self.assertEqual(data["context_refs"], ["voucher:12"])
        self.assertEqual(data["steps"][0]["tool_name"], "record_voucher")
        self.assertEqual(self.handler.requests[0].thread_id, "thread-1")

    def test_history_endpoints_use_accounting_prefix(self):
        """历史查询接口使用 /api/accounting 前缀。"""
        turns = self.client.get("/api/accounting/thread-1/turns")
        steps = self.client.get("/api/accounting/thread-1/collaboration-steps")
        events = self.client.get("/api/accounting/thread-1/events")

        self.assertEqual(turns.status_code, 200)
        self.assertEqual(steps.status_code, 200)
        self.assertEqual(events.status_code, 200)
        self.assertEqual(steps.json()[0]["tool_name"], "audit_voucher")
        self.assertEqual(events.json()[0]["event_type"], "tool_call")

    def test_health(self):
        """健康检查可用。"""
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
