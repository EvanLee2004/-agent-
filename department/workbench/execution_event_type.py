"""执行事件类型枚举。"""

from enum import Enum


class ExecutionEventType(Enum):
    """执行事件类型枚举。

    描述事件的性质，用于在协作摘要中区分不同类型的步骤。
    """

    #: crewAI Agent 调用会计工具（如 record_voucher、query_vouchers）
    TOOL_CALL = "tool_call"
    #: 工具执行结果（由 crewAI 工具包装器记录）
    TOOL_RESULT = "tool_result"
    #: 会计部门固定任务步骤
    TASK_CALL = "task_call"
    #: 最终 AI 文本回复（用于无工具调用时的 fallback）
    FINAL_REPLY = "final_reply"
