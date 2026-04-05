"""FastAPI API 端点测试。

测试真实的 api.deerflow_app: FastAPI 应用，验证：
- HTTP 契约（响应结构、状态码）
- 错误翻译（AppConversationHandler 将 ConversationError → HTTP 400，Exception → HTTP 500）
- collaboration_steps 字段出现在响应模型中

本测试通过 create_app() 注入 mock router 和 mock workbench_service，
实现完全 hermetic（不触发真实 DeerFlow 调用）。

测试层次：
1. endpoint 层：测试路由定义和响应模型
2. AppConversationHandler 层：测试真实的错误翻译逻辑（通过注入 mock router）
"""

import unittest
from unittest.mock import MagicMock, patch

from conversation.conversation_error import ConversationError
from conversation.conversation_request import ConversationRequest
from conversation.conversation_response import ConversationResponse
from department.workbench.collaboration_step import CollaborationStep
from department.workbench.collaboration_step_type import CollaborationStepType
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.deerflow_app import create_app


def create_test_app_with_mock_handler():
    """创建测试用 FastAPI 应用，注入 mock 依赖。

    不触发真实 DeerFlow 配置或 LLM 调用。
    """
    mock_router = MagicMock()
    mock_workbench = MagicMock()

    return create_app(
        conversation_handler=mock_router,
        workbench_service=mock_workbench,
    ), mock_router, mock_workbench


class TestAPIEndpointsContract(unittest.TestCase):
    """验证 API 端点的 HTTP 契约。"""

    def setUp(self):
        app, mock_router, mock_workbench = create_test_app_with_mock_handler()
        self._app = app
        self._client = TestClient(app, raise_server_exceptions=False)
        self._mock_router = mock_router
        self._mock_workbench = mock_workbench

    def test_health_returns_ok_and_version(self):
        """GET /health 返回 status=ok 和 version 字段。"""
        response = self._client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("version", data)

    def test_reply_validates_empty_user_input(self):
        """POST /reply 对空 user_input 返回 422 验证错误。

        请求体只包含 user_input（thread_id 通过路径参数传入）。
        """
        response = self._client.post(
            "/api/conversations/test-thread-1/reply",
            json={"user_input": ""},
        )
        self.assertEqual(response.status_code, 422)

    def test_reply_validates_missing_user_input(self):
        """POST /reply 缺少 user_input 返回 422。"""
        response = self._client.post(
            "/api/conversations/test-thread/reply",
            json={},
        )
        self.assertEqual(response.status_code, 422)

    def test_reply_returns_conversation_response(self):
        """POST /reply 成功时返回 conversation 响应结构。"""
        self._mock_router.handle.return_value = ConversationResponse(
            reply_text="测试回复",
            collaboration_steps=[
                CollaborationStep(
                    goal="测试目标",
                    step_type=CollaborationStepType.FINAL_REPLY,
                    tool_name="",
                    summary="测试摘要",
                )
            ],
        )
        response = self._client.post(
            "/api/conversations/test-thread/reply",
            json={"user_input": "测试"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("reply_text", data)
        self.assertIn("collaboration_steps", data)
        self.assertIn("thread_id", data)
        self.assertEqual(data["reply_text"], "测试回复")

    def test_reply_contains_collaboration_steps_fields(self):
        """POST /reply 响应中 collaboration_steps 每项包含 goal/step_type/tool_name/summary。"""
        self._mock_router.handle.return_value = ConversationResponse(
            reply_text="完成",
            collaboration_steps=[
                CollaborationStep(
                    goal="记录收款",
                    step_type=CollaborationStepType.TOOL_CALL,
                    tool_name="record_voucher",
                    summary="凭证已记录",
                )
            ],
        )
        response = self._client.post(
            "/api/conversations/test-thread/reply",
            json={"user_input": "记录收款"},
        )
        self.assertEqual(response.status_code, 200)
        steps = response.json()["collaboration_steps"]
        self.assertEqual(len(steps), 1)
        step = steps[0]
        self.assertIn("goal", step)
        self.assertIn("step_type", step)
        self.assertIn("tool_name", step)
        self.assertIn("summary", step)
        self.assertEqual(step["tool_name"], "record_voucher")

    def test_get_turns_returns_list_with_structure(self):
        """GET /turns 返回列表，每项包含 thread_id/original_user_input/reply_text/collaboration_steps。"""
        self._mock_workbench.list_turns_with_steps.return_value = [
            {
                "turn_id": "turn-1",
                "turn_index": 1,
                "original_user_input": "记录收款",
                "reply_text": "已完成",
                "collaboration_steps": [
                    CollaborationStep(
                        goal="记录收款",
                        step_type=CollaborationStepType.TOOL_CALL,
                        tool_name="record_voucher",
                        summary="凭证已记录",
                    )
                ],
            }
        ]
        response = self._client.get("/api/conversations/test-thread/turns")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        turn = data[0]
        self.assertIn("thread_id", turn)
        self.assertIn("original_user_input", turn)
        self.assertIn("reply_text", turn)
        self.assertIn("collaboration_steps", turn)

    def test_get_turns_empty_for_unknown_thread(self):
        """GET /turns 对未知 thread_id 返回空列表。"""
        self._mock_workbench.list_turns_with_steps.return_value = []
        response = self._client.get("/api/conversations/unknown-thread/turns")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 0)

    def test_get_collaboration_steps_returns_list(self):
        """GET /collaboration-steps 返回列表，每项包含 goal/step_type/tool_name/summary。"""
        self._mock_workbench.list_collaboration_steps.return_value = [
            CollaborationStep(
                goal="记录收款",
                step_type=CollaborationStepType.TOOL_CALL,
                tool_name="record_voucher",
                summary="凭证已记录",
            )
        ]
        response = self._client.get("/api/conversations/test-thread/collaboration-steps")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        step = data[0]
        self.assertIn("goal", step)
        self.assertIn("step_type", step)
        self.assertIn("tool_name", step)
        self.assertIn("summary", step)

    def test_get_collaboration_steps_empty_for_unknown_thread(self):
        """GET /collaboration-steps 对未知 thread_id 返回空列表。"""
        self._mock_workbench.list_collaboration_steps.return_value = []
        response = self._client.get("/api/conversations/unknown-thread/collaboration-steps")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 0)

    def test_get_events_returns_list_with_turn_context(self):
        """GET /events 返回列表，每项包含 event_type/tool_name/summary/turn_index/event_sequence。"""
        self._mock_workbench.list_execution_events_with_context.return_value = [
            {
                "event_type": "tool_call",
                "tool_name": "record_voucher",
                "summary": "调用 record_voucher",
                "turn_index": 1,
                "event_sequence": 1,
            },
            {
                "event_type": "tool_result",
                "tool_name": "record_voucher",
                "summary": "凭证已记录",
                "turn_index": 1,
                "event_sequence": 2,
            },
        ]
        response = self._client.get("/api/conversations/test-thread/events")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)
        evt = data[0]
        self.assertIn("event_type", evt)
        self.assertIn("tool_name", evt)
        self.assertIn("summary", evt)
        self.assertIn("turn_index", evt)
        self.assertIn("event_sequence", evt)
        self.assertIsInstance(evt["turn_index"], int)
        self.assertIsInstance(evt["event_sequence"], int)

    def test_get_events_empty_for_unknown_thread(self):
        """GET /events 对未知 thread_id 返回空列表。"""
        self._mock_workbench.list_execution_events_with_context.return_value = []
        response = self._client.get("/api/conversations/unknown-thread/events")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 0)


@patch("app.conversation_request_handler.logger")
class TestAppConversationHandlerErrorTranslation(unittest.TestCase):
    """验证 AppConversationHandler 的真实错误翻译逻辑。

    通过注入 mock router 来测试真实的错误翻译行为，
    logger.exception 被 patch 为静默，以避免测试输出噪音。

    测试目标：
    - ConversationError → HTTP 400
    - 普通 Exception → HTTP 500
    - 不泄露 traceback / api_key / deerflow / config 等敏感词
    """

    def _build_real_handler_with_mock_router(self):
        """构造真实的 AppConversationHandler，内部 router 是 mock。"""
        from app.conversation_request_handler import AppConversationHandler
        from conversation.conversation_router import ConversationRouter
        from runtime.deerflow.finance_department_tool_context import FinanceDepartmentToolContext

        mock_inner_router = MagicMock(spec=ConversationRouter)
        fake_tool_context = MagicMock(spec=FinanceDepartmentToolContext)

        handler = AppConversationHandler(
            router=mock_inner_router,
            tool_context=fake_tool_context,
        )
        return handler, mock_inner_router

    def test_conversation_error_becomes_http_400(self, mock_logger=None):
        """内部 router 抛出 ConversationError → AppConversationHandler 翻译为 HTTP 400。"""
        handler, mock_router = self._build_real_handler_with_mock_router()
        business_error_msg = "凭证不存在"
        mock_router.handle.side_effect = ConversationError(business_error_msg)

        app = create_app(conversation_handler=handler, workbench_service=MagicMock())
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/conversations/test-thread/reply",
            json={"user_input": "测试"},
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("detail", data)
        self.assertEqual(data["detail"], business_error_msg)
        self.assertNotIn("Traceback", data["detail"])

    def test_generic_exception_becomes_http_500(self, mock_logger=None):
        """内部 router 抛出普通 Exception → AppConversationHandler 翻译为 HTTP 500。"""
        handler, mock_router = self._build_real_handler_with_mock_router()
        mock_router.handle.side_effect = RuntimeError("DeerFlow connection failed")

        app = create_app(conversation_handler=handler, workbench_service=MagicMock())
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/conversations/test-thread/reply",
            json={"user_input": "测试"},
        )

        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertIn("detail", data)
        self.assertEqual(data["detail"], "服务暂时不可用，请稍后重试。")
        self.assertNotIn("Traceback", data["detail"])
        self.assertNotIn("traceback", data["detail"].lower())
        self.assertNotIn("deerflow", data["detail"].lower())
        self.assertNotIn("config", data["detail"].lower())
        self.assertNotIn("api_key", data["detail"].lower())
        self.assertNotIn("api key", data["detail"].lower())

    def test_conversation_error_detail_not_generic_message(self, mock_logger=None):
        """ConversationError 的 detail 应该是原始业务错误，不是通用"服务暂时不可用"。"""
        handler, mock_router = self._build_real_handler_with_mock_router()
        business_errors = [
            "凭证不存在",
            "金额不合法：必须为正数",
            "日期格式错误，应为 YYYY-MM-DD",
        ]
        mock_router.handle.side_effect = ConversationError(business_errors[0])

        app = create_app(conversation_handler=handler, workbench_service=MagicMock())
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/conversations/test-thread/reply",
            json={"user_input": "测试"},
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["detail"], business_errors[0])
        self.assertNotEqual(data["detail"], "服务暂时不可用，请稍后重试。")

    def test_no_sensitive_leak_on_unknown_exception(self, mock_logger=None):
        """未知异常（如 DeerFlow 底层错误）的响应不泄露敏感信息。"""
        handler, mock_router = self._build_real_handler_with_mock_router()
        sensitive_exceptions = [
            Exception("DeerFlow config error: api_key=sk-xxx"),
            Exception("LLM call failed: config not found for model"),
            Exception("DeerFlow runtime error: /path/to/config.yaml"),
        ]
        mock_router.handle.side_effect = sensitive_exceptions[0]

        app = create_app(conversation_handler=handler, workbench_service=MagicMock())
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/conversations/test-thread/reply",
            json={"user_input": "测试"},
        )

        self.assertEqual(response.status_code, 500)
        detail = response.json()["detail"]
        self.assertEqual(detail, "服务暂时不可用，请稍后重试。")
        self.assertNotIn("sk-xxx", detail)
        self.assertNotIn("api_key", detail)
        self.assertNotIn("config.yaml", detail)
        self.assertNotIn("config", detail.lower())


@patch("app.cli_conversation_handler.logger")
class TestCliConversationHandlerErrorTranslation(unittest.TestCase):
    """验证 CliConversationHandler 的错误翻译逻辑。

    ConversationError → 直接使用 str(e)（用户可理解的中文业务描述）
    其他 Exception → 通用友好文案。logger.exception 被 patch 为静默，
    以避免测试输出噪音。
    """

    def _build_real_cli_handler_with_mock_router(self):
        """构造真实的 CliConversationHandler，内部 router 是 mock。"""
        from app.cli_conversation_handler import CliConversationHandler
        from conversation.conversation_router import ConversationRouter
        from runtime.deerflow.finance_department_tool_context import FinanceDepartmentToolContext

        mock_inner_router = MagicMock(spec=ConversationRouter)
        fake_tool_context = MagicMock(spec=FinanceDepartmentToolContext)

        handler = CliConversationHandler(
            router=mock_inner_router,
            tool_context=fake_tool_context,
        )
        return handler, mock_inner_router

    def test_conversation_error_preserves_business_message(self, mock_logger=None):
        """ConversationError 的消息应该直接透传给用户（不套通用文案）。"""
        handler, mock_router = self._build_real_cli_handler_with_mock_router()
        business_error_msg = "凭证不存在"
        mock_router.handle.side_effect = ConversationError(business_error_msg)

        request = ConversationRequest(user_input="测试", thread_id="test-thread")
        response = handler.handle(request)

        self.assertEqual(response.reply_text, business_error_msg)
        self.assertNotEqual(response.reply_text, "服务暂时不可用，请稍后重试。")

    def test_generic_exception_returns_generic_message(self, mock_logger=None):
        """普通异常返回通用友好文案。"""
        handler, mock_router = self._build_real_cli_handler_with_mock_router()
        mock_router.handle.side_effect = RuntimeError("internal error")

        request = ConversationRequest(user_input="测试", thread_id="test-thread")
        response = handler.handle(request)

        self.assertEqual(response.reply_text, "服务暂时不可用，请稍后重试。")

    def test_conversation_error_with_various_business_messages(self, mock_logger=None):
        """各种业务错误消息都应该直接透传。"""
        handler, mock_router = self._build_real_cli_handler_with_mock_router()
        business_messages = [
            "凭证不存在",
            "金额不合法：必须为正数",
            "日期格式错误，应为 YYYY-MM-DD",
            "该凭证已审核，无法修改",
        ]
        for msg in business_messages:
            mock_router.handle.side_effect = ConversationError(msg)
            request = ConversationRequest(user_input="测试", thread_id="test-thread")
            response = handler.handle(request)
            self.assertEqual(response.reply_text, msg, f"Expected '{msg}' but got '{response.reply_text}'")


if __name__ == "__main__":
    unittest.main()
