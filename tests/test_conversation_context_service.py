"""会计部门会话上下文服务测试。"""

import unittest

from conversation.tool_router_response import ToolRouterResponse
from department.conversation_context_service import ConversationContextService


class FakeWorkbenchService:
    """测试用工作台服务。"""

    def list_turns_with_steps(self, thread_id: str):
        """返回固定历史回合。"""
        return [
            {
                "turn_index": 1,
                "original_user_input": "记录销售收入",
                "reply_text": "凭证 12 已记录。",
            }
        ]

    def list_execution_events_with_context(self, thread_id: str):
        """返回固定工具结果事件。"""
        return [
            {
                "event_type": "tool_result",
                "tool_name": "record_voucher",
                "summary": ToolRouterResponse(
                    tool_name="record_voucher",
                    success=True,
                    payload={"voucher_id": 12},
                    voucher_ids=[12],
                    context_refs=["voucher:12"],
                ).to_tool_message_content(),
            }
        ]


class ConversationContextServiceTest(unittest.TestCase):
    """验证多轮上下文引用解析。"""

    def test_resolves_latest_voucher_reference(self):
        """用户说“刚才那张”时应解析最近凭证候选。"""
        service = ConversationContextService(FakeWorkbenchService())

        context = service.build_context("thread-1", "复核刚才那张凭证")

        self.assertEqual(context.context_refs, ["voucher:12"])
        self.assertIn("第 1 轮", context.summary)
        self.assertIn("voucher:12", context.summary)

    def test_does_not_create_reference_without_hint(self):
        """没有指代词时不应强行绑定历史凭证。"""
        service = ConversationContextService(FakeWorkbenchService())

        context = service.build_context("thread-1", "查询本月凭证")

        self.assertEqual(context.context_refs, [])


if __name__ == "__main__":
    unittest.main()
