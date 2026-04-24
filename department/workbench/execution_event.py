"""执行事件模型。

描述 crewAI 会计部门执行过程中产生的、可用于生成用户可见协作摘要的单个事件。

这些事件由固定任务投影和 crewAI 工具包装器记录，不包含原始长文本 thinking，只包含
对用户有意义的结构化信息：工具调用名称、任务委托动作、系统结论等。
"""

from dataclasses import dataclass

from department.workbench.execution_event_type import ExecutionEventType


@dataclass(frozen=True)
class ExecutionEvent:
    """描述 crewAI 会计部门中的一个可摘要事件。

    Attributes:
        event_type: 事件类型，区分工具调用、任务委托、最终回复等。
        tool_name: 被调用的工具名称（仅 tool_call/task_call 时有值）。
        summary: 对用户可见的简短描述，由仓储层根据事件数据生成。
            不包含原始长文本 thinking。
    """

    event_type: ExecutionEventType
    tool_name: str
    summary: str
