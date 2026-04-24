"""SQLite 会计部门工作台仓储实现（多回合版本）。

支持按线程存储多回合历史，包括：
- 每轮的原始用户输入、最终回复、token 使用量
- 每轮的协作步骤（CollaborationStep 列表）
- 每轮的内部执行事件（ExecutionEvent 列表）

设计原则：
- 每次 finalize_turn 在 turns 表产生一条新记录（turn_index 自增）
- 同一 thread_id 的 turn_index 从 1 开始递增

内存暂存策略：
- save() / get() 操作内存中的 _pending_workbench，不产生 DB 记录
- save_turn()（由 finalize_turn 调用）才真正落 DB，产生一条 turns 记录
- 查询方法（list_turns_with_steps / list_collaboration_steps / list_execution_events_with_context）只查 DB
- 不覆盖历史，通过 turn_index 排序查询
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from department.llm_usage import LlmUsage
from department.workbench.collaboration_step import CollaborationStep
from department.workbench.collaboration_step_type import CollaborationStepType
from department.workbench.department_workbench import DepartmentWorkbench
from department.workbench.department_workbench_repository import DepartmentWorkbenchRepository
from department.workbench.execution_event import ExecutionEvent
from department.workbench.execution_event_type import ExecutionEventType


# Schema: 多回合历史表
_CREATE_TURNS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS turns (
    turn_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    original_user_input TEXT NOT NULL,
    reply_text TEXT NOT NULL DEFAULT '',
    usage_json TEXT,
    created_at TEXT DEFAULT (datetime('now', 'utc'))
)
"""

_CREATE_STEPS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS turn_collaboration_steps (
    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    step_type TEXT NOT NULL,
    tool_name TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL,
    FOREIGN KEY (turn_id) REFERENCES turns(turn_id) ON DELETE CASCADE
)
"""

_CREATE_EVENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS turn_execution_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    tool_name TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL,
    FOREIGN KEY (turn_id) REFERENCES turns(turn_id) ON DELETE CASCADE
)
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_turns_thread ON turns(thread_id, turn_index);
CREATE INDEX IF NOT EXISTS idx_steps_turn ON turn_collaboration_steps(turn_id);
CREATE INDEX IF NOT EXISTS idx_events_turn ON turn_execution_events(turn_id);
"""


def _now_utc() -> str:
    """返回当前 UTC 时间（ISO 格式 Z 后缀）。"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _serialize_usage(usage: LlmUsage | None) -> str | None:
    if usage is None:
        return None
    return json.dumps(
        {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
        },
        ensure_ascii=False,
    )


def _deserialize_usage(raw: str | None) -> LlmUsage | None:
    if raw is None:
        return None
    u = json.loads(raw)
    return LlmUsage(
        input_tokens=u["input_tokens"],
        output_tokens=u["output_tokens"],
        total_tokens=u["total_tokens"],
    )


class SQLiteDepartmentWorkbenchRepository(DepartmentWorkbenchRepository):
    """SQLite 版工作台仓储（多回合持久化版本）。

    提供：
    - save_turn()：保存一轮完整对话（含协作步骤和执行事件）
    - list_turns_with_steps()：获取某线程全部历史回合（含每轮协作步骤）
    - list_collaboration_steps()：获取某线程全部回合的协作步骤
    - list_execution_events_with_context()：获取某线程全部回合的执行事件（含上下文）
    - clear_thread()：清除某线程全部历史（仅用于测试清理）

    数据库文件路径固定（在 DepartmentOrchestrationFactory 层决定），
    所有 API 请求共享同一数据库实例。

    内存暂存策略：
    - _pending_workbench：暂存当前正在累积中的工作台（未 finalize）
    - save() / get() 只操作 _pending_workbench，不产生 DB 记录
    - save_turn()（由 finalize_turn 调用）才真正落 DB
    """

    def __init__(self, database_path: str | Path):
        """构造仓储。

        Args:
            database_path: SQLite 数据库文件路径（API 场景使用固定路径）。
        """
        self._database_path = Path(database_path)
        self._init_db()
        # 内存暂存：thread_id -> DepartmentWorkbench（正在累积，未 finalize）
        self._pending_workbench: dict[str, DepartmentWorkbench] = {}

    def _init_db(self) -> None:
        """初始化数据库表。"""
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as conn:
            conn.executescript(_CREATE_TURNS_TABLE_SQL)
            conn.executescript(_CREATE_STEPS_TABLE_SQL)
            conn.executescript(_CREATE_EVENTS_TABLE_SQL)
            conn.executescript(_CREATE_INDEX_SQL)

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接。"""
        return sqlite3.connect(str(self._database_path))

    def save_turn(
        self,
        thread_id: str,
        original_user_input: str,
        reply_text: str,
        usage: LlmUsage | None,
        collaboration_steps: list[CollaborationStep],
        execution_events: list[ExecutionEvent],
    ) -> str:
        """保存一轮完整对话。

        在 turns 表插入新记录（turn_index 自增），
        并在 turn_collaboration_steps 和 turn_execution_events 表保存关联数据。

        Args:
            thread_id: 线程标识。
            original_user_input: 原始用户输入。
            reply_text: crewAI 会计部门最终回复文本。
            usage: LLM token 使用量（内部遥测）。
            collaboration_steps: 协作步骤列表（用户可见投影）。
            execution_events: 执行事件列表（内部遥测）。

        Returns:
            本轮生成的 turn_id。
        """
        turn_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            # 计算本线程当前最大 turn_index，新值为 +1
            cursor = conn.execute(
                "SELECT COALESCE(MAX(turn_index), 0) FROM turns WHERE thread_id = ?",
                (thread_id,),
            )
            next_index = (cursor.fetchone()[0] or 0) + 1

            conn.execute(
                """
                INSERT INTO turns
                    (turn_id, thread_id, turn_index, original_user_input, reply_text, usage_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn_id,
                    thread_id,
                    next_index,
                    original_user_input,
                    reply_text,
                    _serialize_usage(usage),
                    _now_utc(),
                ),
            )

            # 保存协作步骤
            for step in collaboration_steps:
                conn.execute(
                    """
                    INSERT INTO turn_collaboration_steps
                        (turn_id, goal, step_type, tool_name, summary)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (turn_id, step.goal, step.step_type.value, step.tool_name, step.summary),
                )

            # 保存执行事件（内部遥测）
            for evt in execution_events:
                conn.execute(
                    """
                    INSERT INTO turn_execution_events
                        (turn_id, event_type, tool_name, summary)
                    VALUES (?, ?, ?, ?)
                    """,
                    (turn_id, evt.event_type.value, evt.tool_name, evt.summary),
                )

            conn.commit()
        return turn_id

    def list_turns_with_steps(self, thread_id: str) -> list[dict]:
        """列出某线程全部回合（含每轮的协作步骤）。

        Returns:
            列表，每项包含 turns 表字段加上 collaboration_steps 子列表。
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    t.turn_id,
                    t.turn_index,
                    t.original_user_input,
                    t.reply_text,
                    t.usage_json,
                    t.created_at,
                    s.goal,
                    s.step_type,
                    s.tool_name,
                    s.summary
                FROM turns t
                LEFT JOIN turn_collaboration_steps s ON s.turn_id = t.turn_id
                WHERE t.thread_id = ?
                ORDER BY t.turn_index ASC, s.step_id ASC
                """,
                (thread_id,),
            )
            rows = cursor.fetchall()

        # 按 turn_id 分组
        turns_map: dict[str, dict] = {}
        for row in rows:
            turn_id = row[0]
            if turn_id not in turns_map:
                turns_map[turn_id] = {
                    "turn_id": row[0],
                    "turn_index": row[1],
                    "original_user_input": row[2],
                    "reply_text": row[3],
                    "usage": _deserialize_usage(row[4]),
                    "created_at": row[5],
                    "collaboration_steps": [],
                }
            # s.goal 为 None 表示该 turn 无步骤
            if row[6] is not None:
                turns_map[turn_id]["collaboration_steps"].append(
                    CollaborationStep(
                        goal=row[6],
                        step_type=CollaborationStepType(row[7]),
                        tool_name=row[8] or "",
                        summary=row[9],
                    )
                )
        return list(turns_map.values())

    def list_collaboration_steps(self, thread_id: str) -> list[CollaborationStep]:
        """列出某线程全部回合的协作步骤（扁平列表，按 turn_index 排序）。"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT s.goal, s.step_type, s.tool_name, s.summary
                FROM turn_collaboration_steps s
                JOIN turns t ON t.turn_id = s.turn_id
                WHERE t.thread_id = ?
                ORDER BY t.turn_index ASC, s.step_id ASC
                """,
                (thread_id,),
            )
            rows = cursor.fetchall()
        return [
            CollaborationStep(
                goal=row[0],
                step_type=CollaborationStepType(row[1]),
                tool_name=row[2],
                summary=row[3],
            )
            for row in rows
        ]

    def list_execution_events_with_context(
        self, thread_id: str
    ) -> list[dict]:
        """列出某线程全部回合的内部执行事件（含回合归属上下文）。

        Returns:
            每条事件包含：
            - event_type, tool_name, summary（与 ExecutionEvent 字段一致）
            - turn_index：事件所属回合的序号
            - event_sequence：事件在该回合内的顺序（从 1 开始）
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    e.event_type,
                    e.tool_name,
                    e.summary,
                    t.turn_index,
                    e.event_id
                FROM turn_execution_events e
                JOIN turns t ON t.turn_id = e.turn_id
                WHERE t.thread_id = ?
                ORDER BY t.turn_index ASC, e.event_id ASC
                """,
                (thread_id,),
            )
            rows = cursor.fetchall()

        events: list[dict] = []
        current_turn_index: int | None = None
        sequence_in_turn: int = 0
        for row in rows:
            turn_index = row[3]
            if turn_index != current_turn_index:
                current_turn_index = turn_index
                sequence_in_turn = 0
            sequence_in_turn += 1
            events.append({
                "event_type": row[0],
                "tool_name": row[1],
                "summary": row[2],
                "turn_index": turn_index,
                "event_sequence": sequence_in_turn,
            })
        return events

    def clear_thread(self, thread_id: str) -> None:
        """清除某线程全部历史（用于测试清理）。"""
        self._pending_workbench.pop(thread_id, None)
        with self._get_connection() as conn:
            conn.execute("DELETE FROM turn_collaboration_steps WHERE turn_id IN (SELECT turn_id FROM turns WHERE thread_id = ?)", (thread_id,))
            conn.execute("DELETE FROM turn_execution_events WHERE turn_id IN (SELECT turn_id FROM turns WHERE thread_id = ?)", (thread_id,))
            conn.execute("DELETE FROM turns WHERE thread_id = ?", (thread_id,))
            conn.commit()

    # 以下为“当前回合暂存”接口实现。
    # save()/get() 只操作 _pending_workbench（内存暂存），不直接产生 DB 记录；
    # 真正的历史持久化仍由 save_turn() 负责。

    def save(self, workbench: DepartmentWorkbench) -> None:
        """保存工作台（内存暂存，不产生 DB 记录）。

        在 SQLite 实现中，save() 只更新内存 pending。
        要将数据持久化到 DB，需调用 save_turn()（由 finalize_turn 调用）。
        """
        self._pending_workbench[workbench.thread_id] = workbench

    def get(self, thread_id: str) -> Optional[DepartmentWorkbench]:
        """读取工作台（返回 pending 数据，无 DB 查询）。"""
        return self._pending_workbench.get(thread_id)
