"""DeerFlow 仓储层协作事件回归测试。

验证仓储从 DeerFlow stream 事件正确生成 execution_events，
确保协作摘要来自真实 DeerFlow 事件而非 reply_text 的二次压缩。

DeerFlow stream() 产生的事件类型：
- messages-tuple (type=ai, content=...): AI 文本片段
- messages-tuple (type=ai, tool_calls=[{name, args, id}]): AI 发起工具调用
  注意：tool_calls 项是 {"name": ..., "args": ..., "id": ...}，没有嵌套 "function"
- messages-tuple (type=tool, content=..., name=..., tool_call_id=...): 工具执行结果
  tool_call_id 与原始 tool_calls 项的 id 字段对应
- end: 流结束
"""

import unittest
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from conversation.reply_text_sanitizer import ReplyTextSanitizer
from department.department_role_request import DepartmentRoleRequest
from department.department_runtime_context import DepartmentRuntimeContext
from runtime.deerflow.deerflow_department_role_runtime_repository import (
    DeerFlowDepartmentRoleRuntimeRepository,
)
from runtime.deerflow.deerflow_runtime_assets_service import DeerFlowRuntimeAssetsService


@dataclass
class FakeStreamEvent:
    """模拟 DeerFlow stream() 返回的单个事件。"""
    type: str
    data: dict


class FakeDeerFlowClientForCollaborationEvents:
    """模拟产生完整协作事件序列的 DeerFlow client。

    生成一个真实的 DeerFlow turn，包含：
    1. AI 中间话术（不发最终 reply_text）
    2. AI 调用 generate_fiscal_task_prompt 工具
    3. 工具返回 prompt 内容
    4. AI 调用 task 工具
    5. 工具返回任务 ID
    6. AI 最终回复
    """

    def __init__(self, final_reply: str):
        self._final_reply = final_reply
        self.calls: list[tuple[str, str | None]] = []

    def reset_agent(self) -> None:
        pass

    def stream(self, message: str, *, thread_id: str | None = None):
        self.calls.append((message, thread_id))

        # 第一个 AI 事件：中间话术
        yield FakeStreamEvent(
            type="messages-tuple",
            data={"type": "ai", "content": "好的，我先准备 prompt。", "id": "msg-1"},
        )

        # 第二个 AI 事件：发起 generate_fiscal_task_prompt 工具调用
        # DeerFlow tool_calls 结构: {"name": ..., "args": ..., "id": ...}
        yield FakeStreamEvent(
            type="messages-tuple",
            data={
                "type": "ai",
                "content": "",
                "id": "msg-2",
                "tool_calls": [
                    {"name": "generate_fiscal_task_prompt", "args": {"mode": "bookkeeping"}, "id": "call-1"}
                ],
            },
        )

        # 工具执行结果
        yield FakeStreamEvent(
            type="messages-tuple",
            data={
                "type": "tool",
                "content": '{"prompt": "请帮我记录一笔收款凭证..."}',
                "name": "generate_fiscal_task_prompt",
                "tool_call_id": "call-1",
                "id": "tool-1",
            },
        )

        # 第三个 AI 事件：发起 task 工具调用（DeerFlow task/subagent）
        yield FakeStreamEvent(
            type="messages-tuple",
            data={
                "type": "ai",
                "content": "",
                "id": "msg-3",
                "tool_calls": [
                    {"name": "task", "args": {"task_id": "subagent-1"}, "id": "call-2"}
                ],
            },
        )

        # task 工具执行结果
        yield FakeStreamEvent(
            type="messages-tuple",
            data={
                "type": "tool",
                "content": '{"status": "started", "task_id": "subagent-1"}',
                "name": "task",
                "tool_call_id": "call-2",
                "id": "tool-2",
            },
        )

        # 最终 AI 回复（唯一应进入 reply_text 的内容）
        yield FakeStreamEvent(
            type="messages-tuple",
            data={"type": "ai", "content": self._final_reply, "id": "msg-4"},
        )

        # 结束事件
        yield FakeStreamEvent(
            type="end",
            data={"usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}},
        )


class FakeDeerFlowClientWithNoToolCalls:
    """模拟没有任何工具调用的简单 turn。"""

    def __init__(self, reply_text: str):
        self._reply_text = reply_text

    def reset_agent(self) -> None:
        pass

    def stream(self, message: str, *, thread_id: str | None = None):
        # 直接返回最终回复
        yield FakeStreamEvent(
            type="messages-tuple",
            data={"type": "ai", "content": self._reply_text, "id": "msg-1"},
        )
        yield FakeStreamEvent(
            type="end",
            data={"usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}},
        )


class DeerFlowDepartmentRoleRuntimeRepositoryCollaborationTest(unittest.TestCase):
    """验证 DeerFlow 仓储正确从 stream 事件生成 execution_events。"""

    def _build_repository(self, client):
        """构造只依赖假 client 的仓储。"""
        # 使用 patch 跳过 LlmConfiguration 的完整构造
        runtime_context = DepartmentRuntimeContext()
        runtime_assets_service = MagicMock(spec=DeerFlowRuntimeAssetsService)
        client_factory = MagicMock()
        client_factory.create_client.return_value = client
        with patch.object(
            DeerFlowDepartmentRoleRuntimeRepository,
            "_get_assets",
            return_value=MagicMock(),
        ):
            repo = DeerFlowDepartmentRoleRuntimeRepository(
                configuration=MagicMock(),
                runtime_assets_service=runtime_assets_service,
                client_factory=client_factory,
                runtime_context=runtime_context,
                reply_text_sanitizer=ReplyTextSanitizer(),
            )
        # 直接注入假 client 缓存
        repo._clients["coordinator"] = client
        return repo

    def test_execution_events_from_full_collaboration_stream(self):
        """验证完整协作流产生正确的 execution_events 序列。

        事件序列：generate_fiscal_task_prompt → tool_result → task → tool_result → final_reply
        期望 execution_events：
        1. TOOL_CALL (generate_fiscal_task_prompt)
        2. TOOL_RESULT (generate_fiscal_task_prompt result)
        3. TASK_CALL (task)
        4. TOOL_RESULT (task result)
        5. FINAL_REPLY (最终回复)
        """
        final_reply = "已为你记录收款凭证，凭证号 #1。"
        client = FakeDeerFlowClientForCollaborationEvents(final_reply)
        repo = self._build_repository(client)

        request = DepartmentRoleRequest(
            role_name="coordinator",
            user_input="记录一笔收款",
            thread_id="test-thread",
            collaboration_depth=0,
        )
        response = repo.reply(request)

        # reply_text 只取最后一个非空 AI 文本
        self.assertEqual(response.reply_text, final_reply)

        # execution_events 应包含 5 个事件
        self.assertEqual(len(response.execution_events), 5)

        # 事件 1: generate_fiscal_task_prompt 调用
        self.assertEqual(response.execution_events[0].event_type.value, "tool_call")
        self.assertEqual(response.execution_events[0].tool_name, "generate_fiscal_task_prompt")
        self.assertIn("调用", response.execution_events[0].summary)

        # 事件 2: generate_fiscal_task_prompt 结果
        self.assertEqual(response.execution_events[1].event_type.value, "tool_result")
        self.assertEqual(response.execution_events[1].tool_name, "generate_fiscal_task_prompt")
        # 仓储层保留原始 content 截断（用于未来扩展），不暴露给用户
        self.assertIn("prompt", response.execution_events[1].summary)

        # 事件 3: task 调用
        self.assertEqual(response.execution_events[2].event_type.value, "task_call")
        self.assertEqual(response.execution_events[2].tool_name, "task")
        self.assertIn("调用", response.execution_events[2].summary)

        # 事件 4: task 结果
        self.assertEqual(response.execution_events[3].event_type.value, "tool_result")
        self.assertEqual(response.execution_events[3].tool_name, "task")
        # 仓储层保留原始 content（用于未来扩展），不在此处验证用户可见输出
        self.assertIn("task_id", response.execution_events[3].summary)

        # 事件 5: FINAL_REPLY（即使有工具调用，也仍保留最终结论）
        self.assertEqual(response.execution_events[4].event_type.value, "final_reply")
        self.assertEqual(response.execution_events[4].tool_name, "")
        self.assertEqual(response.execution_events[4].summary, final_reply)

    def test_reply_text_only_takes_last_non_empty_ai_text(self):
        """验证 reply_text 只取最后一个非空 AI 文本，不受中间 tool 事件影响。"""
        final_reply = "这是最终回复。"
        client = FakeDeerFlowClientForCollaborationEvents(final_reply)
        repo = self._build_repository(client)

        request = DepartmentRoleRequest(
            role_name="coordinator",
            user_input="记账",
            thread_id="test-thread",
            collaboration_depth=0,
        )
        response = repo.reply(request)

        # reply_text 不应是中间话术"好的，我先准备 prompt。"
        self.assertNotIn("好的，我先准备 prompt", response.reply_text)
        self.assertEqual(response.reply_text, final_reply)

    def test_no_tool_calls_yields_final_reply_as_single_event(self):
        """验证无工具调用时，直接以 FINAL_REPLY 作为单步骤。"""
        reply_text = "你好，我是智能财务部门协调员。"
        client = FakeDeerFlowClientWithNoToolCalls(reply_text)
        repo = self._build_repository(client)

        request = DepartmentRoleRequest(
            role_name="coordinator",
            user_input="你是谁",
            thread_id="test-thread",
            collaboration_depth=0,
        )
        response = repo.reply(request)

        self.assertEqual(response.reply_text, reply_text)
        self.assertEqual(len(response.execution_events), 1)
        self.assertEqual(response.execution_events[0].event_type.value, "final_reply")
        self.assertEqual(response.execution_events[0].summary, reply_text)

    def test_tool_result_summary_truncates_long_content(self):
        """验证工具结果摘要会截断过长内容。"""

        class FakeClientWithLongResult:
            def reset_agent(self):
                pass

            def stream(self, message: str, *, thread_id: str | None = None):
                # 工具返回超长内容（> 80 字符）
                long_content = "A" * 200
                yield FakeStreamEvent(
                    type="messages-tuple",
                    data={
                        "type": "ai",
                        "content": "",
                        "id": "msg-1",
                        "tool_calls": [
                            {"name": "query_vouchers", "args": {}, "id": "call-1"}
                        ],
                    },
                )
                yield FakeStreamEvent(
                    type="messages-tuple",
                    data={
                        "type": "tool",
                        "content": long_content,
                        "name": "query_vouchers",
                        "tool_call_id": "call-1",
                        "id": "tool-1",
                    },
                )
                yield FakeStreamEvent(
                    type="messages-tuple",
                    data={"type": "ai", "content": "查询完成。", "id": "msg-2"},
                )

        repo = self._build_repository(FakeClientWithLongResult())
        response = repo.reply(
            DepartmentRoleRequest(
                role_name="coordinator",
                user_input="查询凭证",
                thread_id="test-thread",
                collaboration_depth=0,
            )
        )

        # 工具结果摘要应被截断（max 80 chars + "…"）
        tool_result_event = response.execution_events[1]
        self.assertLessEqual(len(tool_result_event.summary), 81)
        self.assertTrue(tool_result_event.summary.endswith("…"))

    def test_factory_sanitizes_tool_result_no_raw_json_leaks_to_cli(self):
        """验证 CollaborationStepFactory 将原始 tool result 转换为用户友好摘要。

        仓储层保留原始 content（用于未来扩展），factory 层将其转换为
        标准化中文结论。确保最终 collaboration_steps 不暴露原始 JSON。
        """
        from department.workbench.collaboration_step_factory import CollaborationStepFactory
        from department.workbench.execution_event import ExecutionEvent
        from department.workbench.execution_event_type import ExecutionEventType
        from department.workbench.role_trace_summary_builder import RoleTraceSummaryBuilder

        factory = CollaborationStepFactory(RoleTraceSummaryBuilder())

        # 模拟仓储层返回的原始 raw content
        raw_events = [
            ExecutionEvent(
                event_type=ExecutionEventType.TOOL_CALL,
                tool_name="generate_fiscal_task_prompt",
                summary="调用 generate_fiscal_task_prompt",
            ),
            ExecutionEvent(
                event_type=ExecutionEventType.TOOL_RESULT,
                tool_name="generate_fiscal_task_prompt",
                # 原始 JSON content，factory 应将其转换为标准化结论
                summary='{"prompt": "请帮我记录一笔收款凭证，金额 1000 元..."}',
            ),
            ExecutionEvent(
                event_type=ExecutionEventType.TASK_CALL,
                tool_name="task",
                summary="调用 task",
            ),
            ExecutionEvent(
                event_type=ExecutionEventType.TOOL_RESULT,
                tool_name="task",
                # 原始 task result JSON
                summary='{"status": "started", "task_id": "subagent-1", "result": {...}}',
            ),
            ExecutionEvent(
                event_type=ExecutionEventType.FINAL_REPLY,
                tool_name="",
                summary="已完成所有操作。",
            ),
        ]

        steps = factory.build_from_events(
            goal="记录收款",
            execution_events=raw_events,
            final_reply_text="已完成所有操作。",
        )

        # 验证最终 collaboration_steps 不包含原始 JSON
        step_summaries = [s.summary for s in steps]
        self.assertNotIn('{"prompt"', " ".join(step_summaries))
        self.assertNotIn('{"status"', " ".join(step_summaries))
        self.assertNotIn("subagent-1", " ".join(step_summaries))
        self.assertNotIn("请帮我记录", " ".join(step_summaries))

        # 验证 TOOL_RESULT 被映射为标准化中文结论
        tool_result_summaries = [
            s.summary for s in steps if s.step_type.value == "tool_result"
        ]
        self.assertIn("财务任务 prompt 已生成", tool_result_summaries)
        self.assertIn("子代理任务已返回结果", tool_result_summaries)
