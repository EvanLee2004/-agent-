"""部门工作台服务多回合测试。"""

import tempfile
import unittest

from department.llm_usage import LlmUsage
from department.workbench.collaboration_step import CollaborationStep
from department.workbench.collaboration_step_type import CollaborationStepType
from department.workbench.execution_event import ExecutionEvent
from department.workbench.execution_event_type import ExecutionEventType
from department.workbench.sqlite_department_workbench_repository import (
    SQLiteDepartmentWorkbenchRepository,
)
from department.workbench.department_workbench_service import DepartmentWorkbenchService


class TestDepartmentWorkbenchServiceMultiTurn(unittest.TestCase):
    """验证 DepartmentWorkbenchService 的多回合持久化能力。"""

    def _make_service(self, tmpdir: str) -> DepartmentWorkbenchService:
        repo = SQLiteDepartmentWorkbenchRepository(f"{tmpdir}/workbench.db")
        return DepartmentWorkbenchService(repo)

    def test_finalize_turn_persists_to_db(self):
        """验证 finalize_turn 将数据写入 DB。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            svc = self._make_service(tmpdir)

            svc.start_turn("thread-1", "第一轮输入")
            svc.record_collaboration_step(
                "thread-1",
                CollaborationStep(
                    goal="记录凭证",
                    step_type=CollaborationStepType.TOOL_CALL,
                    tool_name="record_voucher",
                    summary="凭证已记录",
                ),
            )
            svc.finalize_turn(
                "thread-1",
                reply_text="第一轮回复",
                usage=LlmUsage(input_tokens=10, output_tokens=5, total_tokens=15),
                execution_events=[
                    ExecutionEvent(
                        event_type=ExecutionEventType.TOOL_CALL,
                        tool_name="record_voucher",
                        summary="开始",
                    )
                ],
            )

            # 通过 list_turns_with_steps 验证持久化
            turns = svc.list_turns_with_steps("thread-1")
            self.assertEqual(len(turns), 1)
            self.assertEqual(turns[0]["reply_text"], "第一轮回复")
            self.assertEqual(turns[0]["usage"].total_tokens, 15)
            self.assertEqual(len(turns[0]["collaboration_steps"]), 1)

    def test_multi_turn_increment_turn_index(self):
        """验证多轮时 turn_index 递增。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            svc = self._make_service(tmpdir)

            # 第一轮
            svc.start_turn("mthread", "输入1")
            svc.finalize_turn(
                "mthread",
                reply_text="回复1",
                usage=None,
                execution_events=[],
            )
            # 第二轮
            svc.start_turn("mthread", "输入2")
            svc.finalize_turn(
                "mthread",
                reply_text="回复2",
                usage=None,
                execution_events=[],
            )

            turns = svc.list_turns_with_steps("mthread")
            self.assertEqual(len(turns), 2)
            self.assertEqual(turns[0]["turn_index"], 1)
            self.assertEqual(turns[1]["turn_index"], 2)
            self.assertEqual(turns[0]["reply_text"], "回复1")
            self.assertEqual(turns[1]["reply_text"], "回复2")

    def test_list_turns_with_steps_via_service(self):
        """验证 service.list_turns_with_steps 返回带步骤的回合。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            svc = self._make_service(tmpdir)

            svc.start_turn("steps-svc", "用户输入")
            svc.record_collaboration_step(
                "steps-svc",
                CollaborationStep(
                    goal="目标",
                    step_type=CollaborationStepType.TOOL_CALL,
                    tool_name="record_voucher",
                    summary="已记录",
                ),
            )
            svc.finalize_turn(
                "steps-svc",
                reply_text="回复",
                usage=None,
                execution_events=[],
            )

            turns = svc.list_turns_with_steps("steps-svc")
            self.assertEqual(len(turns), 1)
            self.assertEqual(len(turns[0]["collaboration_steps"]), 1)
            self.assertEqual(turns[0]["collaboration_steps"][0].tool_name, "record_voucher")

    def test_list_execution_events_with_context_via_service(self):
        """验证 service.list_execution_events_with_context 返回带上下文的事件列表。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            svc = self._make_service(tmpdir)

            svc.start_turn("events-svc", "输入")
            svc.finalize_turn(
                "events-svc",
                reply_text="回复",
                usage=None,
                execution_events=[
                    ExecutionEvent(
                        event_type=ExecutionEventType.TOOL_CALL,
                        tool_name="record_voucher",
                        summary="开始",
                    ),
                    ExecutionEvent(
                        event_type=ExecutionEventType.TOOL_RESULT,
                        tool_name="record_voucher",
                        summary="结束",
                    ),
                ],
            )

            events = svc.list_execution_events_with_context("events-svc")
            self.assertEqual(len(events), 2)
            # list_execution_events_with_context 返回的 event_type 是字符串
            self.assertEqual(events[0]["event_type"], "tool_call")
            self.assertEqual(events[1]["event_type"], "tool_result")
            self.assertEqual(events[0]["turn_index"], 1)

    def test_list_collaboration_steps_via_service(self):
        """验证 service.list_collaboration_steps 返回扁平步骤列表。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            svc = self._make_service(tmpdir)

            svc.start_turn("collab-svc", "输入")
            svc.record_collaboration_step(
                "collab-svc",
                CollaborationStep(
                    goal="目标",
                    step_type=CollaborationStepType.TOOL_CALL,
                    tool_name="record_voucher",
                    summary="步骤1",
                ),
            )
            svc.record_collaboration_step(
                "collab-svc",
                CollaborationStep(
                    goal="目标",
                    step_type=CollaborationStepType.FINAL_REPLY,
                    tool_name="",
                    summary="步骤2",
                ),
            )
            svc.finalize_turn(
                "collab-svc",
                reply_text="回复",
                usage=None,
                execution_events=[],
            )

            steps = svc.list_collaboration_steps("collab-svc")
            self.assertEqual(len(steps), 2)
            self.assertEqual(steps[0].tool_name, "record_voucher")
            self.assertEqual(steps[1].step_type, CollaborationStepType.FINAL_REPLY)

    def test_clear_thread_via_service(self):
        """验证 clear_thread 清除所有数据。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            svc = self._make_service(tmpdir)

            svc.start_turn("clear-svc", "输入")
            svc.record_collaboration_step(
                "clear-svc",
                CollaborationStep(
                    goal="目标",
                    step_type=CollaborationStepType.FINAL_REPLY,
                    tool_name="",
                    summary="完成",
                ),
            )
            svc.finalize_turn(
                "clear-svc",
                reply_text="回复",
                usage=None,
                execution_events=[
                    ExecutionEvent(
                        event_type=ExecutionEventType.TOOL_RESULT,
                        tool_name="tool",
                        summary="完成",
                    )
                ],
            )

            svc._repository.clear_thread("clear-svc")

            turns = svc.list_turns_with_steps("clear-svc")
            self.assertEqual(len(turns), 0)
            events = svc.list_execution_events_with_context("clear-svc")
            self.assertEqual(len(events), 0)


if __name__ == "__main__":
    unittest.main()
