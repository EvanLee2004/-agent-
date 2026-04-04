"""执行事件类型枚举。"""

from enum import Enum


class ExecutionEventType(Enum):
    """执行事件类型枚举。

    描述事件的性质，用于在协作摘要中区分不同类型的步骤。
    """

    #: AI 调用工具（如 generate_fiscal_task_prompt、task）
    TOOL_CALL = "tool_call"
    #: 工具执行结果（DeerFlow stream 返回 ToolMessage）
    TOOL_RESULT = "tool_result"
    #: DeerFlow task/subagent 委托
    TASK_CALL = "task_call"
    #: 最终 AI 文本回复（用于无工具调用时的 fallback）
    FINAL_REPLY = "final_reply"