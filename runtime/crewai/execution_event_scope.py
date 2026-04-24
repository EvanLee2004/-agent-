"""crewAI 执行事件作用域。"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from department.workbench.execution_event import ExecutionEvent


_CURRENT_EXECUTION_EVENTS: ContextVar[list[ExecutionEvent] | None] = ContextVar(
    "CURRENT_EXECUTION_EVENTS",
    default=None,
)


@contextmanager
def open_execution_event_scope() -> Iterator[list[ExecutionEvent]]:
    """打开一次 crewAI 执行事件收集作用域。

    工具包装器会在执行前后追加 TOOL_CALL / TOOL_RESULT 事件。事件列表跟随
    当前请求的 ContextVar，而不是挂在工具对象上，原因是 crewAI 工具对象会被
    多个 Agent/Task 复用；把事件放进工具实例会破坏请求隔离。
    """
    events: list[ExecutionEvent] = []
    token = _CURRENT_EXECUTION_EVENTS.set(events)
    try:
        yield events
    finally:
        _CURRENT_EXECUTION_EVENTS.reset(token)


def append_execution_event(event: ExecutionEvent) -> None:
    """向当前作用域追加执行事件。"""
    events = _CURRENT_EXECUTION_EVENTS.get()
    if events is not None:
        events.append(event)
