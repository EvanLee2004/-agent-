"""SQLite 工作台仓储测试。"""

import tempfile
import unittest

from department.llm_usage import LlmUsage
from department.workbench.collaboration_step import CollaborationStep
from department.workbench.collaboration_step_type import CollaborationStepType
from department.workbench.department_workbench import DepartmentWorkbench
from department.workbench.execution_event import ExecutionEvent
from department.workbench.execution_event_type import ExecutionEventType
from department.workbench.sqlite_department_workbench_repository import (
    SQLiteDepartmentWorkbenchRepository,
)


class TestSQLiteDepartmentWorkbenchRepository(unittest.TestCase):
    """验证 SQLite 工作台仓储的持久化和读取。"""

    def test_save_and_get_workbench(self):
        """验证 save/get 操作内存暂存（不写 DB）。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteDepartmentWorkbenchRepository(f"{tmpdir}/workbench.db")
            workbench = DepartmentWorkbench(
                thread_id="test-thread-1",
                original_user_input="记录一笔收款",
                collaboration_steps=[
                    CollaborationStep(
                        goal="记录一笔收款",
                        step_type=CollaborationStepType.TOOL_CALL,
                        tool_name="record_voucher",
                        summary="调用 record_voucher",
                    ),
                    CollaborationStep(
                        goal="记录一笔收款",
                        step_type=CollaborationStepType.FINAL_REPLY,
                        tool_name="",
                        summary="凭证已记录",
                    ),
                ],
                reply_text="好的，已为你记录收款凭证。",
                usage=LlmUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            )
            repo.save(workbench)

            retrieved = repo.get("test-thread-1")
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.thread_id, "test-thread-1")
            self.assertEqual(retrieved.original_user_input, "记录一笔收款")
            self.assertEqual(len(retrieved.collaboration_steps), 2)
            self.assertEqual(retrieved.reply_text, "好的，已为你记录收款凭证。")
            self.assertIsNotNone(retrieved.usage)
            self.assertEqual(retrieved.usage.total_tokens, 150)

    def test_save_updates_existing_workbench(self):
        """验证重复 save() 会覆盖 pending 工作台（内存行为）。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteDepartmentWorkbenchRepository(f"{tmpdir}/workbench.db")
            wb1 = DepartmentWorkbench(
                thread_id="test-thread-2",
                original_user_input="第一次输入",
                collaboration_steps=[],
            )
            repo.save(wb1)
            wb2 = DepartmentWorkbench(
                thread_id="test-thread-2",
                original_user_input="第一次输入",
                collaboration_steps=[
                    CollaborationStep(
                        goal="第一次输入",
                        step_type=CollaborationStepType.FINAL_REPLY,
                        tool_name="",
                        summary="已处理",
                    )
                ],
                reply_text="处理完成",
                usage=LlmUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            )
            repo.save(wb2)

            retrieved = repo.get("test-thread-2")
            self.assertEqual(len(retrieved.collaboration_steps), 1)
            self.assertEqual(retrieved.reply_text, "处理完成")
            self.assertEqual(retrieved.usage.total_tokens, 15)

    def test_get_nonexistent_returns_none(self):
        """验证获取不存在的工作台返回 None。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteDepartmentWorkbenchRepository(f"{tmpdir}/workbench.db")
            self.assertIsNone(repo.get("nonexistent-thread"))

    def test_workbench_without_usage(self):
        """验证 usage 为 None 时可以正常保存和读取。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteDepartmentWorkbenchRepository(f"{tmpdir}/workbench.db")
            workbench = DepartmentWorkbench(
                thread_id="test-thread-3",
                original_user_input="查询凭证",
                collaboration_steps=[],
                reply_text="查询结果如下：",
                usage=None,
            )
            repo.save(workbench)
            retrieved = repo.get("test-thread-3")
            self.assertIsNone(retrieved.usage)
            self.assertEqual(retrieved.reply_text, "查询结果如下：")

    def test_multi_turn_persistence(self):
        """验证多回合持久化：同一 thread_id 保存多轮，每轮 turn_index 自增。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteDepartmentWorkbenchRepository(f"{tmpdir}/workbench.db")

            # 第一轮
            repo.save_turn(
                thread_id="multi-turn-thread",
                original_user_input="第一轮输入",
                reply_text="第一轮回复",
                usage=LlmUsage(input_tokens=10, output_tokens=5, total_tokens=15),
                collaboration_steps=[
                    CollaborationStep(
                        goal="第一轮目标",
                        step_type=CollaborationStepType.TOOL_CALL,
                        tool_name="tool_a",
                        summary="tool_a 结果",
                    )
                ],
                execution_events=[],
            )

            # 第二轮
            repo.save_turn(
                thread_id="multi-turn-thread",
                original_user_input="第二轮输入",
                reply_text="第二轮回复",
                usage=LlmUsage(input_tokens=20, output_tokens=10, total_tokens=30),
                collaboration_steps=[
                    CollaborationStep(
                        goal="第二轮目标",
                        step_type=CollaborationStepType.FINAL_REPLY,
                        tool_name="",
                        summary="第二轮完成",
                    )
                ],
                execution_events=[],
            )

            # 通过 list_turns_with_steps 验证回合数
            turns = repo.list_turns_with_steps("multi-turn-thread")
            self.assertEqual(len(turns), 2)
            self.assertEqual(turns[0]["turn_index"], 1)
            self.assertEqual(turns[1]["turn_index"], 2)
            self.assertEqual(turns[0]["reply_text"], "第一轮回复")
            self.assertEqual(turns[1]["reply_text"], "第二轮回复")

    def test_list_turns_with_steps(self):
        """验证 list_turns_with_steps 返回每轮关联的协作步骤。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteDepartmentWorkbenchRepository(f"{tmpdir}/workbench.db")
            repo.save_turn(
                thread_id="steps-thread",
                original_user_input="用户输入",
                reply_text="回复",
                usage=None,
                collaboration_steps=[
                    CollaborationStep(
                        goal="目标A",
                        step_type=CollaborationStepType.TOOL_CALL,
                        tool_name="record_voucher",
                        summary="凭证已记录",
                    ),
                    CollaborationStep(
                        goal="目标A",
                        step_type=CollaborationStepType.FINAL_REPLY,
                        tool_name="",
                        summary="完成",
                    ),
                ],
                execution_events=[],
            )

            turns = repo.list_turns_with_steps("steps-thread")
            self.assertEqual(len(turns), 1)
            self.assertEqual(len(turns[0]["collaboration_steps"]), 2)
            self.assertEqual(turns[0]["collaboration_steps"][0].tool_name, "record_voucher")
            self.assertEqual(turns[0]["collaboration_steps"][1].step_type, CollaborationStepType.FINAL_REPLY)

    def test_list_execution_events_with_context(self):
        """验证 list_execution_events_with_context 返回带上下文的事件列表。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteDepartmentWorkbenchRepository(f"{tmpdir}/workbench.db")
            repo.save_turn(
                thread_id="events-thread",
                original_user_input="输入",
                reply_text="回复",
                usage=None,
                collaboration_steps=[],
                execution_events=[
                    ExecutionEvent(
                        event_type=ExecutionEventType.TOOL_CALL,
                        tool_name="record_voucher",
                        summary="开始执行 record_voucher",
                    ),
                    ExecutionEvent(
                        event_type=ExecutionEventType.TOOL_RESULT,
                        tool_name="record_voucher",
                        summary="record_voucher 执行完成",
                    ),
                ],
            )

            events = repo.list_execution_events_with_context("events-thread")
            self.assertEqual(len(events), 2)
            # list_execution_events_with_context 返回的 event_type 是字符串
            self.assertEqual(events[0]["event_type"], "tool_call")
            self.assertEqual(events[1]["event_type"], "tool_result")
            self.assertEqual(events[0]["tool_name"], "record_voucher")
            self.assertEqual(events[0]["turn_index"], 1)
            self.assertEqual(events[0]["event_sequence"], 1)
            self.assertEqual(events[1]["event_sequence"], 2)

    def test_list_execution_events_empty(self):
        """验证无 execution_events 时返回空列表。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteDepartmentWorkbenchRepository(f"{tmpdir}/workbench.db")
            repo.save_turn(
                thread_id="no-events-thread",
                original_user_input="输入",
                reply_text="回复",
                usage=None,
                collaboration_steps=[],
                execution_events=[],
            )

            events = repo.list_execution_events_with_context("no-events-thread")
            self.assertEqual(len(events), 0)

    def test_clear_thread(self):
        """验证 clear_thread 清除所有历史数据。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteDepartmentWorkbenchRepository(f"{tmpdir}/workbench.db")
            repo.save_turn(
                thread_id="clear-thread",
                original_user_input="输入",
                reply_text="回复",
                usage=None,
                collaboration_steps=[
                    CollaborationStep(
                        goal="目标",
                        step_type=CollaborationStepType.FINAL_REPLY,
                        tool_name="",
                        summary="完成",
                    )
                ],
                execution_events=[
                    ExecutionEvent(
                        event_type=ExecutionEventType.TOOL_RESULT,
                        tool_name="tool",
                        summary="完成",
                    )
                ],
            )

            repo.clear_thread("clear-thread")

            turns = repo.list_turns_with_steps("clear-thread")
            self.assertEqual(len(turns), 0)
            steps = repo.list_collaboration_steps("clear-thread")
            self.assertEqual(len(steps), 0)
            events = repo.list_execution_events_with_context("clear-thread")
            self.assertEqual(len(events), 0)


if __name__ == "__main__":
    unittest.main()
